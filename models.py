from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Strategy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    display_name = db.Column(db.String(100), nullable=False)
    tier = db.Column(db.String(20), nullable=True) # Tier 1, Tier 2, etc.
    color = db.Column(db.String(20), nullable=True) # hex or css var

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), nullable=False)
    strategy = db.Column(db.String(50), nullable=False) 
    entry_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=True)
    daily_change = db.Column(db.Float, nullable=True)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        roi = 0
        if self.entry_price and self.current_price:
            roi = ((self.current_price - self.entry_price) / self.entry_price) * 100
            
        return {
            'id': self.id,
            'ticker': self.ticker,
            'strategy': self.strategy,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'daily_change': self.daily_change if self.daily_change is not None else 0.0,
            'added_date': self.added_date.strftime('%Y-%m-%d %H:%M:%S') if self.added_date else datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'roi': round(roi, 2)
        }
