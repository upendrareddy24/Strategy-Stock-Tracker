try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    Image = None

import os
import yfinance as yf
import pandas as pd
import re
import json
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def fetch_stock_catalyst(ticker, daily_change, hist_df=None, include_news=True):
    """Fetches recent news and technical indicators to explain the move."""
    if not client:
        return "Connect Gemini API to see catalyst."

    try:
        stock = yf.Ticker(ticker)
        # 1. News is expensive - skip if we are in a rush (manual add)
        headlines = []
        if include_news:
            try:
                news = stock.news[:2] 
                headlines = [n.get('title', '') for n in news]
            except: pass
        
        # 2. Use existing history or fetch 6mo
        hist = hist_df
        if hist is None or hist.empty:
            hist = stock.history(period="6mo")
            
        if hist.empty:
            return "Consolidating."
            
        current_price = float(hist['Close'].iloc[-1])
        vol_today = int(hist['Volume'].iloc[-1])
        
        # Indicators from the SAME dataframe
        sma50 = hist['Close'].tail(50).mean()
        ema8 = hist['Close'].ewm(span=8, adjust=False).mean().iloc[-1]
        ema21 = hist['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
        
        # Squeeze Detection (Bollinger Band Compression)
        std_dev = hist['Close'].tail(20).std()
        avg_20 = hist['Close'].tail(20).mean()
        bb_width = ((avg_20 + 2*std_dev) - (avg_20 - 2*std_dev)) / current_price
        
        # RSI 14
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))

        technical_summary = f"Price: ${current_price:.2f}, EMA 8/21: {ema8:.2f}/{ema21:.2f}, RSI: {rsi:.1f}, BB Width: {bb_width:.3f}"
        direction = "up" if daily_change >= 0 else "down"
        
        news_part = f" News: {json.dumps(headlines)}." if headlines else " No major news found."
        prompt = f"Explain why {ticker} moved {daily_change:.2f}% ({direction}). Techs: {technical_summary}.{news_part} One short sentence (max 15 words)."
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Error fetching catalyst for {ticker}: {e}")
        return "Technical consolidation."

def fetch_current_price(ticker):
    """Combined fetcher for price, daily change, volume, and RVOL with optimized network calls."""
    try:
        stock = yf.Ticker(ticker)
        # Fetch 6 months of data in ONE call - enough for RVOL (20d), EMA (21), SMA50 (50), etc.
        hist = stock.history(period="6mo") 
        
        if hist.empty:
            return None
            
        current_price = float(hist['Close'].iloc[-1])
        volume = int(hist['Volume'].iloc[-1])
        
        # Relative Volume (RVOL) - calculated from the SAME dataframe
        if len(hist) > 11:
            avg_volume = hist['Volume'].iloc[-11:-1].mean()
            rel_volume = round(volume / avg_volume, 2) if avg_volume > 0 else 1.0
        else:
            rel_volume = 1.0
            
        # Daily change
        daily_change = 0.0
        if len(hist) >= 2:
            prev_close = float(hist['Close'].iloc[-2])
            daily_change = float(((current_price - prev_close) / prev_close) * 100)
            
        return {
            'price': current_price,
            'daily_change': daily_change,
            'volume': volume,
            'relative_volume': rel_volume,
            'hist_df': hist # Pass the DF along to avoid re-fetching
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
        df = None
        if file_path.endswith('.csv'):
            try:
                df = pd.read_csv(file_path, header=None, sep=None, engine='python', on_bad_lines='skip')
                # Try again with proper headers if first row looks like headers
                df_header = pd.read_csv(file_path, sep=None, engine='python', on_bad_lines='skip')
                if any(col.lower() in ['symbol', 'ticker'] for col in df_header.columns):
                    df = df_header
            except: pass
        else:
            try:
                df = pd.read_excel(file_path)
            except: pass

        if df is not None and not df.empty:
            # Map columns
            col_map = {}
            for col in df.columns:
                c_low = str(col).lower()
                if 'symbol' in c_low or 'ticker' in c_low: col_map['ticker'] = col
                if 'last' in c_low or 'price' in c_low: col_map['price'] = col
                if '%change' in c_low or 'change' in c_low: col_map['change'] = col
                if 'volume_nsort' in c_low or 'volume_sort' in c_low: col_map['rvol'] = col
            
            results = []
            if 'ticker' in col_map:
                for _, row in df.iterrows():
                    ticker = str(row[col_map['ticker']]).strip().upper()
                    if ticker and re.match(r'^[A-Z]{1,6}$', ticker) and ticker not in ['SYMBOL', 'TICKER']:
                        # Extract data
                        price = 0.0
                        change = 0.0
                        rvol = 1.0
                        
                        try:
                            if 'price' in col_map:
                                price_val = str(row[col_map['price']]).replace('$', '').replace(',', '')
                                price = float(price_val)
                            if 'change' in col_map:
                                chg_val = str(row[col_map['change']]).replace('%', '').replace('+', '')
                                change = float(chg_val)
                            if 'rvol' in col_map:
                                rvol = float(row[col_map['rvol']])
                        except: pass
                        
                        results.append({
                            'ticker': ticker,
                            'price': price,
                            'daily_change': change,
                            'relative_volume': rvol
                        })
                if results: return results

        # Fallback to Ticker SCAN only (if column mapping failed or not an Excel structure)
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            raw_matches = re.findall(r'\b[A-Z]{1,6}\b', content)
            ignore_set = {'WATCHLIST', 'SYMBOL', 'DESCRIPTION', 'LAST', 'PRICE', 'CHANGE', 'VOLUME', 'HIGH', 'LOW', 'OPEN', 'CLOSE', 'NET', 'CHG'}
            tickers = []
            seen = set()
            for m in raw_matches:
                if m not in ignore_set and m not in seen:
                    tickers.append({'ticker': m})
                    seen.add(m)
            return tickers
            
    except Exception as e:
        print(f"ERROR: process_excel: {e}")
        return []
