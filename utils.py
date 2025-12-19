try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    Image = None

import yfinance as yf
import pandas as pd
import re
import os

def fetch_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Try to get price
        info = stock.info
        price = info.get('regularMarketPrice') or info.get('currentPrice')
        
        if not price:
            # Fallback to history for fast_info or history
            hist = stock.history(period="1d")
            if not hist.empty:
                price = hist['Close'].iloc[-1]
        return price
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None

def process_screenshot(file_path):
    if not pytesseract or not Image:
        print("pytesseract or PIL not installed. Cannot process screenshot.")
        return []
        
    try:
        text = pytesseract.image_to_string(Image.open(file_path))
        tickers = re.findall(r'\b[A-Z]{1,5}\b', text)
        return list(set(tickers))
    except Exception as e:
        print(f"Error processing screenshot: {e}")
        return []

def process_excel(file_path):
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        # Look for a 'Ticker' or 'Symbol' column
        ticker_col = next((col for col in df.columns if col.lower() in ['ticker', 'symbol', 'stock']), None)
        if ticker_col:
            return df[ticker_col].dropna().astype(str).tolist()
        return []
    except Exception as e:
        print(f"Error processing excel: {e}")
        return []
