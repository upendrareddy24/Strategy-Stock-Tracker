import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from models import db, Stock, Strategy
from utils import fetch_current_price, process_screenshot, process_excel, fetch_stock_catalyst
from datetime import datetime

app = Flask(__name__)
CORS(app)
basedir = os.path.abspath(os.path.dirname(__file__))
db_dir = os.path.join(basedir, 'instance')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or \
    'sqlite:///' + os.path.join(db_dir, 'stocks.db')

if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)

# Default Strategies from user list
DEFAULT_STRATEGIES = [
    {"name": "2HK_Gainers", "display_name": "2HK_Gainers", "tier": "Tier 1", "color": "#f85149"},
    {"name": "2HK_RVOL_SQ", "display_name": "2HK_RVOL_SQ", "tier": "Tier 2", "color": "#3fb950"},
    {"name": "2HvolHK", "display_name": "2HvolHK", "tier": "Tier 3", "color": "#58a6ff"},
    {"name": "2SQ_Bull_HK", "display_name": "2SQ_Bull_HK", "tier": "Tier 4", "color": "#bc8cff"},
    {"name": "2_3XvolSq", "display_name": "2_3XvolSq", "tier": "Tier 5", "color": "#ffab00"}
]

with app.app_context():
    db.create_all()
    # Auto-migration: Ensure last_catalyst column exists for old databases
    from sqlalchemy import text
    try:
        db.session.execute(text('ALTER TABLE stock ADD COLUMN last_catalyst TEXT'))
        db.session.commit()
    except: db.session.rollback()
    
    try:
        db.session.execute(text('ALTER TABLE stock ADD COLUMN first_tracked DATETIME'))
        db.session.execute(text('UPDATE stock SET first_tracked = added_date WHERE first_tracked IS NULL'))
        db.session.commit()
    except: db.session.rollback()

    # Populate strategies if empty
    if Strategy.query.count() == 0:
        for s in DEFAULT_STRATEGIES:
            new_strat = Strategy(name=s['name'], display_name=s['display_name'], tier=s['tier'], color=s['color'])
            db.session.add(new_strat)
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    # Sort by date added (newest first)
    stocks = Stock.query.order_by(Stock.added_date.desc()).all()
    return jsonify([s.to_dict() for s in stocks])

@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    strats = Strategy.query.all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'display_name': s.display_name,
        'tier': s.tier,
        'color': s.color
    } for s in strats])

@app.route('/api/rename_strategy', methods=['POST'])
def rename_strategy():
    data = request.json
    strat_id = data.get('id')
    new_name = data.get('display_name')
    
    strat = Strategy.query.get(strat_id)
    if strat:
        strat.display_name = new_name
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Strategy not found'}), 404

@app.route('/api/clear_all', methods=['DELETE'])
def clear_all():
    # Delete all stocks
    Stock.query.delete()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/add_stock', methods=['POST'])
def add_stock():
    data = request.json
    ticker = data.get('ticker').upper()
    strategy = data.get('strategy')
    
    price_data = fetch_current_price(ticker)
    if not price_data:
        return jsonify({'error': 'Could not fetch price for ticker'}), 400
        
    catalyst = fetch_stock_catalyst(ticker, price_data['daily_change'])
    
    # Check for duplicate in same strategy
    existing = Stock.query.filter_by(ticker=ticker, strategy=strategy).first()
    if existing:
        existing.current_price = price_data['price']
        existing.daily_change = price_data['daily_change']
        existing.last_catalyst = catalyst
        existing.added_date = datetime.utcnow() # Update date to move to top
        db.session.commit()
        return jsonify(existing.to_dict())

    new_stock = Stock(
        ticker=ticker,
        strategy=strategy,
        entry_price=price_data['price'],
        current_price=price_data['price'],
        daily_change=price_data['daily_change'],
        last_catalyst=catalyst
    )
    db.session.add(new_stock)
    db.session.commit()
    return jsonify(new_stock.to_dict())

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    strategy = request.form.get('strategy')
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    tickers = []
    if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        tickers = process_screenshot(file_path)
    elif file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        tickers = process_excel(file_path)
        
    added_stocks_objects = []
    for ticker in tickers:
        ticker = ticker.upper()
        if ticker in ['SYMBOL', 'TICKER']:
            continue
            
        price_data = fetch_current_price(ticker)
        if price_data:
            catalyst = fetch_stock_catalyst(ticker, price_data['daily_change'])
            
            # Duplicate check
            existing = Stock.query.filter_by(ticker=ticker, strategy=strategy).first()
            if existing:
                existing.current_price = price_data['price']
                existing.daily_change = price_data['daily_change']
                existing.last_catalyst = catalyst
                existing.added_date = datetime.utcnow()
                added_stocks_objects.append(existing)
            else:
                new_stock = Stock(
                    ticker=ticker,
                    strategy=strategy,
                    entry_price=price_data['price'],
                    current_price=price_data['price'],
                    daily_change=price_data['daily_change'],
                    last_catalyst=catalyst
                )
                db.session.add(new_stock)
                added_stocks_objects.append(new_stock)
            
    db.session.commit()
    return jsonify([s.to_dict() for s in added_stocks_objects])

@app.route('/api/delete_stock/<int:stock_id>', methods=['DELETE'])
def delete_stock(stock_id):
    stock = Stock.query.get(stock_id)
    if stock:
        db.session.delete(stock)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Stock not found'}), 404

@app.route('/api/update_prices', methods=['GET'])
def update_prices():
    stocks = Stock.query.all()
    for stock in stocks:
        price_data = fetch_current_price(stock.ticker)
        if price_data:
            stock.current_price = price_data['price']
            stock.daily_change = price_data['daily_change']
            stock.last_catalyst = fetch_stock_catalyst(stock.ticker, stock.daily_change)
    db.session.commit()
    return jsonify([s.to_dict() for s in stocks])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8001))
    app.run(host='0.0.0.0', port=port, debug=True)
