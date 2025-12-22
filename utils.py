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
        # Get history for today and yesterday close to calculate chance
        hist = stock.history(period="5d") # Get a few days to be safe
        
        if hist.empty:
            return None
            
        current_price = hist['Close'].iloc[-1]
        
        # Calculate daily change
        daily_change = 0.0
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[-2]
            daily_change = ((current_price - prev_close) / prev_close) * 100
            
        return {
            'price': current_price,
            'daily_change': daily_change
        }
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
        # Read without header first to find the best column
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None)
        
        if df.empty:
            return []

        # Strategy 1: Look for a column that has "Symbol" or "Ticker" in any of its first few rows
        for col in df.columns:
            for val in df[col].head(10):
                if str(val).lower() in ['symbol', 'ticker', 'stock']:
                    # Found the column! extract data below it
                    return df[col].dropna().astype(str).tolist()[1:] # Skip header-like row

        # Strategy 2: "Smart Search" - find the column with the most ticker-like values
        ticker_pattern = re.compile(r'^[A-Z]{1,5}$')
        best_col = None
        max_tickers = 0
        
        for col in df.columns:
            count = sum(1 for val in df[col].astype(str) if ticker_pattern.match(val))
            if count > max_tickers:
                max_tickers = count
                best_col = col
        
        if best_col is not None and max_tickers > 0:
            # Filter specifically for the tickers in that column
            return [str(val).upper() for val in df[best_col].astype(str) if ticker_pattern.match(val)]
            
        return []
    except Exception as e:
        print(f"Error processing excel: {e}")
        return []
