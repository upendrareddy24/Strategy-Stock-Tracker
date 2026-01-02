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
    last_catalyst = db.Column(db.Text, nullable=True) # AI-generated reason for move
    first_tracked = db.Column(db.DateTime, default=datetime.utcnow)
    movement_history = db.Column(db.Text, nullable=True) # JSON list of daily % changes
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
            'last_catalyst': self.last_catalyst if self.last_catalyst else "No catalyst found.",
            'added_date': self.added_date.strftime('%Y-%m-%d %H:%M:%S') if self.added_date else datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'first_tracked': self.first_tracked.strftime('%Y-%m-%d %H:%M:%S') if self.first_tracked else datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'movement_history': json.loads(self.movement_history) if self.movement_history else [],
            'roi': round(roi, 2)
        }
