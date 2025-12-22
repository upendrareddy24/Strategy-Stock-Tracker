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
    print(f"DEBUG: Processing file: {file_path}")
    try:
        # Read without header
        if file_path.endswith('.csv'):
            # sep=None with engine='python' lets pandas auto-detect delimiters (tabs, commas, semicolons)
            df = pd.read_csv(file_path, header=None, sep=None, engine='python')
        else:
            df = pd.read_excel(file_path, header=None)
        
        if df.empty:
            print("DEBUG: DataFrame is empty")
            return []

        print(f"DEBUG: DataFrame shape: {df.shape}")
        
        # Broaden pattern for tickers (allow dots like BRK.B, and numbers)
        ticker_pattern = re.compile(r'^[A-Z0-9.]{1,8}$')
        column_results = []

        # Common words to ignore so headers don't get counted as tickers
        ignore_list = ['PRICE', 'LAST', 'CHANGE', 'VOLUME', 'HIGH', 'LOW', 'OPEN', 'CLOSE', 'NET', 'CHG', 'DESC', '8', 'WATCH']

        for col in df.columns:
            col_data = df[col].dropna().astype(str).tolist()
            valid_tickers = []
            
            for item in col_data:
                clean_item = item.strip().upper()
                # Remove common noise prefixes
                clean_item = re.sub(r'^\d+\s+', '', clean_item) # Remove leading numbers + space
                
                if ticker_pattern.match(clean_item) and clean_item not in ignore_list:
                    valid_tickers.append(clean_item)
                else:
                    # Look for ticker-like blocks inside the cell
                    matches = re.findall(r'\b[A-Z0-9.]{1,8}\b', clean_item)
                    for m in matches:
                        if m not in ignore_list and any(c.isalpha() for c in m):
                            valid_tickers.append(m)

            seen = set()
            unique_tickers = [x for x in valid_tickers if not (x in seen or seen.add(x))]
            
            has_keyword = any(any(kw in str(val).lower() for kw in ['symbol', 'ticker', 'stock']) for val in df[col].head(15))
            
            column_results.append({
                'count': len(unique_tickers),
                'tickers': unique_tickers,
                'has_keyword': has_keyword,
                'col_index': col
            })
            print(f"DEBUG: Col {col} - Tickers found: {len(unique_tickers)} | Keyword: {has_keyword}")

        if not column_results:
            return []

        # Sort: Highly weight columns with a lot of tickers, then those with keywords
        column_results.sort(key=lambda x: (x['count'] > 2, x['has_keyword'], x['count']), reverse=True)
        
        best_match = column_results[0]
        print(f"DEBUG: Best column selected: {best_match['col_index']} with {best_match['count']} tickers")
        return best_match['tickers']
            
    except Exception as e:
        print(f"ERROR processing file: {e}")
        return []
