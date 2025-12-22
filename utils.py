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
        # Read without header
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, header=None)
        else:
            df = pd.read_excel(file_path, header=None)
        
        if df.empty:
            return []

        ticker_pattern = re.compile(r'^[A-Z]{1,6}$')
        column_results = []

        for col in df.columns:
            # Drop NaN and convert to string
            col_data = df[col].dropna().astype(str).tolist()
            
            # Extract items matching ticker pattern
            valid_tickers = []
            for item in col_data:
                # Strip and clean: TOS sometimes has symbols like " AAPL" or symbols with prefix
                # We also look for specific letter blocks in case of "8 Symbol"
                clean_item = item.strip().upper()
                if ticker_pattern.match(clean_item):
                    valid_tickers.append(clean_item)
                else:
                    # Fallback: if it's "8 AMZN", try extracting the AMZN part
                    matches = re.findall(r'\b[A-Z]{1,6}\b', clean_item)
                    if matches:
                        valid_tickers.extend(matches)

            # Deduplicate while preserving order (mostly)
            seen = set()
            unique_tickers = [x for x in valid_tickers if not (x in seen or seen.add(x))]
            
            # Check for keywords in this column
            has_keyword = any(any(kw in str(val).lower() for kw in ['symbol', 'ticker', 'stock']) for val in df[col].head(10))
            
            column_results.append({
                'count': len(unique_tickers),
                'tickers': unique_tickers,
                'has_keyword': has_keyword,
                'col_index': col
            })

        if not column_results:
            return []

        # Sort: Primary sort by ticker count, secondary by presence of keyword
        # We want the column with the MOST tickers, especially if it was flagged with a keyword
        column_results.sort(key=lambda x: (x['count'], x['has_keyword']), reverse=True)
        
        best_match = column_results[0]
        if best_match['count'] > 0:
            return best_match['tickers']
            
        return []
    except Exception as e:
        print(f"Error processing excel: {e}")
        return []
