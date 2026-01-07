import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from models import db, Stock, Strategy
from utils import fetch_current_price, process_screenshot, process_excel, fetch_stock_catalyst
from datetime import datetime
import json

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
    {"name": "Strategy_1", "display_name": "Active Strategy 1", "tier": "Input", "color": "#58a6ff"}, # Blue
    {"name": "Strategy_2", "display_name": "Active Strategy 2", "tier": "Input", "color": "#bc8cff"}, # Purple
    {"name": "Strategy_3", "display_name": "Active Strategy 3", "tier": "Input", "color": "#ffab00"}, # Orange
    {"name": "Target_Reached", "display_name": "Target Reached (>= 5%)", "tier": "Winner", "color": "#3fb950"}, # Green
    {"name": "Stop_Loss", "display_name": "Stop Loss / Expired (> 5 Days)", "tier": "Cut", "color": "#f85149"}   # Red
]

with app.app_context():
    db.create_all()
    # Auto-migration logic matches original...
    from sqlalchemy import text
    try:
        db.session.execute(text('ALTER TABLE stock ADD COLUMN last_catalyst TEXT'))
        db.session.commit()
    except: db.session.rollback()
    
    try:
        db.session.execute(text('ALTER TABLE stock ADD COLUMN first_tracked TIMESTAMP'))
        db.session.execute(text('UPDATE stock SET first_tracked = added_date WHERE first_tracked IS NULL'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        try:
            db.session.execute(text('ALTER TABLE stock ADD COLUMN first_tracked DATETIME'))
            db.session.execute(text('UPDATE stock SET first_tracked = added_date WHERE first_tracked IS NULL'))
            db.session.commit()
        except: pass

    try:
        db.session.execute(text('ALTER TABLE stock ADD COLUMN movement_history TEXT'))
        db.session.commit()
    except: db.session.rollback()

    try:
        db.session.execute(text('ALTER TABLE stock ADD COLUMN volume BIGINT'))
        db.session.commit()
    except: db.session.rollback()

    try:
        db.session.execute(text('ALTER TABLE stock ADD COLUMN relative_volume FLOAT'))
        db.session.commit()
    except: db.session.rollback()

    try:
        db.session.execute(text('ALTER TABLE stock ADD COLUMN original_strategy TEXT'))
        # Backfill existing
        db.session.execute(text('UPDATE stock SET original_strategy = strategy WHERE original_strategy IS NULL'))
        db.session.commit()
    except: db.session.rollback()

    # Sync Strategies (previously added logic stays here...)
    existing_strategies = Strategy.query.all()
    default_names = [s['name'] for s in DEFAULT_STRATEGIES]
    # ...

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/export', methods=['GET'])
def export_data():
    import csv
    import io
    from flask import Response
    
    stocks = Stock.query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Ticker', 'Strategy', 'Entry Price', 'Current Price', 'ROI %', 'Daily Change %', 'Volume', 'Rel Vol (RVOL)', 'First Tracked', 'Last Updated', 'Last Catalyst', 'Movement History'])
    
    for s in stocks:
        writer.writerow([
            s.ticker, s.strategy, s.entry_price, s.current_price, 
            round(((s.current_price - s.entry_price)/s.entry_price)*100, 2),
            s.daily_change, s.volume, s.relative_volume, s.first_tracked, s.added_date, s.last_catalyst, s.movement_history
        ])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=strategy_report.csv"}
    )

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
    # ... (existing setup)
    data = request.json
    ticker = data.get('ticker').upper()
    strategy = data.get('strategy')
    
    price_data = fetch_current_price(ticker)
    if not price_data:
        return jsonify({'error': 'Could not fetch price for ticker'}), 400
        
    catalyst = fetch_stock_catalyst(ticker, price_data['daily_change'], hist_df=price_data.get('hist_df'), include_news=False)
    
    existing = Stock.query.filter_by(ticker=ticker, strategy=strategy).first()
    
    if existing:
        # ... (update existing logic)
        history = json.loads(existing.movement_history) if existing.movement_history else []
        history.append(price_data['daily_change'])
        existing.movement_history = json.dumps(history[-10:])
        
        existing.current_price = price_data['price']
        existing.daily_change = price_data['daily_change']
        existing.volume = price_data.get('volume', 0)
        existing.relative_volume = price_data.get('relative_volume', 1.0)
        existing.last_catalyst = catalyst
        existing.added_date = datetime.utcnow()
        if not existing.original_strategy: existing.original_strategy = strategy # Backfill
        db.session.commit()
        return jsonify(existing.to_dict())

    new_stock = Stock(
        ticker=ticker,
        strategy=strategy,
        original_strategy=strategy, # Set origin
        entry_price=price_data['price'],
        current_price=price_data['price'],
        daily_change=price_data['daily_change'],
        volume=price_data.get('volume', 0),
        relative_volume=price_data.get('relative_volume', 1.0),
        movement_history=json.dumps([price_data['daily_change']]),
        last_catalyst=catalyst
    )
    db.session.add(new_stock)
    db.session.commit()
    return jsonify(new_stock.to_dict())

# ... (upload logic skips to update_prices)

@app.route('/api/update_prices', methods=['GET'])
def update_prices():
    stocks = Stock.query.all()
    
    STRAT_TARGET = "Target_Reached"
    STRAT_STOP = "Stop_Loss"
    
    for stock in stocks:
        # Backfill origin if missing
        if not stock.original_strategy:
            stock.original_strategy = stock.strategy

        # Don't Auto-Move if already in outcome bucket
        # BUT continue to update price/catalyst
        if stock.strategy in [STRAT_TARGET, STRAT_STOP]:
            # Just update price for visual tracking
            price_data = fetch_current_price(stock.ticker)
            if price_data:
               stock.current_price = price_data['price']
               stock.daily_change = price_data['daily_change']
            continue

        price_data = fetch_current_price(stock.ticker)
        if price_data:
            # Update history
            history = json.loads(stock.movement_history) if stock.movement_history else []
            history.append(price_data['daily_change'])
            stock.movement_history = json.dumps(history[-10:])
            
            stock.current_price = price_data['price']
            stock.daily_change = price_data['daily_change']
            stock.volume = price_data.get('volume', 0)
            stock.relative_volume = price_data.get('relative_volume', 1.0)
            
            # --- AUTO-MOVE LOGIC ---
            roi = 0
            if stock.entry_price > 0:
                roi = (stock.current_price - stock.entry_price) / stock.entry_price
            
            days_held = (datetime.utcnow() - stock.added_date).days
            
            if roi >= 0.05:
                # Target Reached
                stock.strategy = STRAT_TARGET
                stock.last_catalyst = f"🎯 TARGET HIT: {round(roi*100, 2)}% gain in {days_held} days!"
            
            elif days_held >= 5:
                # Stop Loss / Expired
                stock.strategy = STRAT_STOP
                stock.last_catalyst = f"🛑 STOP/EXPIRED: Held for {days_held} days without reaching target."
            
            # --- AI CATALYST CHECK ---
            is_significant_move = abs(stock.daily_change) > 3.0
            is_missing_data = not stock.last_catalyst or "Connect Gemini" in stock.last_catalyst
            
            if (is_significant_move or is_missing_data) and stock.strategy not in [STRAT_TARGET, STRAT_STOP]:
                stock.last_catalyst = fetch_stock_catalyst(stock.ticker, stock.daily_change)
                
    db.session.commit()
    return jsonify([s.to_dict() for s in stocks])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8001))
    app.run(host='0.0.0.0', port=port, debug=True)
