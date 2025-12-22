import os
from flask import Flask, render_template, request, jsonify
from models import db, Stock
from utils import fetch_current_price, process_screenshot, process_excel
from datetime import datetime

app = Flask(__name__)
# Use absolute path for persistence
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

# Create tables outside the main block so Gunicorn executes it
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    stocks = Stock.query.all()
    return jsonify([s.to_dict() for s in stocks])

@app.route('/api/add_stock', methods=['POST'])
def add_stock():
    data = request.json
    ticker = data.get('ticker').upper()
    strategy = data.get('strategy')
    
    price_data = fetch_current_price(ticker)
    if not price_data:
        return jsonify({'error': 'Could not fetch price for ticker'}), 400
        
    new_stock = Stock(
        ticker=ticker,
        strategy=strategy,
        entry_price=price_data['price'],
        current_price=price_data['price'],
        daily_change=price_data['daily_change']
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
    if file.filename.endswith(('.png', '.jpg', '.jpeg')):
        tickers = process_screenshot(file_path)
    elif file.filename.endswith(('.xlsx', '.xls', '.csv')):
        tickers = process_excel(file_path)
        
    added_stocks = []
    for ticker in tickers:
        ticker = ticker.upper()
        price_data = fetch_current_price(ticker)
        if price_data:
            new_stock = Stock(
                ticker=ticker,
                strategy=strategy,
                entry_price=price_data['price'],
                current_price=price_data['price'],
                daily_change=price_data['daily_change']
            )
            db.session.add(new_stock)
            added_stocks.append(new_stock.to_dict())
            
    db.session.commit()
    return jsonify(added_stocks)

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
    db.session.commit()
    return jsonify([s.to_dict() for s in stocks])

if __name__ == '__main__':
    # Use environment variables for production configuration
    port = int(os.environ.get("PORT", 8001))
    debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug)
