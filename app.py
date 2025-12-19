import os
from flask import Flask, render_template, request, jsonify
from models import db, Stock
from utils import fetch_current_price, process_screenshot, process_excel
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_DATA_URI'] = 'sqlite:///stocks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)

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
    
    price = fetch_current_price(ticker)
    if not price:
        return jsonify({'error': 'Could not fetch price for ticker'}), 400
        
    new_stock = Stock(
        ticker=ticker,
        strategy=strategy,
        entry_price=price,
        current_price=price
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
        price = fetch_current_price(ticker)
        if price:
            new_stock = Stock(
                ticker=ticker,
                strategy=strategy,
                entry_price=price,
                current_price=price
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
        price = fetch_current_price(stock.ticker)
        if price:
            stock.current_price = price
    db.session.commit()
    return jsonify([s.to_dict() for s in stocks])

if __name__ == '__main__':
    with app.app_context():
        # Correctly set the database URI before creating tables
        # Actually app.config['SQLALCHEMY_DATABASE_URI'] was misspelled in my thought process but let's fix it here
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stocks.db'
        db.create_all()
    app.run(debug=True, port=8001)
