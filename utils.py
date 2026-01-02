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

def fetch_stock_catalyst(ticker, daily_change):
    """Fetches recent news and technical indicators to explain the move."""
    if not client:
        return "Connect Gemini API to see catalyst."

    try:
        stock = yf.Ticker(ticker)
        # 1. Fetch Fundamental News
        news = stock.news[:3] 
        headlines = [n.get('title', '') for n in news]
        
        # 2. Fetch Technical Context (1 Year of data for SMA calculation)
        hist = stock.history(period="1y")
        if hist.empty:
            return "No data found."
            
        current_price = float(hist['Close'].iloc[-1])
        vol_today = int(hist['Volume'].iloc[-1])
        avg_vol = hist['Volume'].tail(20).mean()
        rvol = round(vol_today / avg_vol, 2)
        
        # Indicators
        sma50 = hist['Close'].tail(50).mean()
        sma200 = hist['Close'].tail(200).mean()
        ema8 = hist['Close'].ewm(span=8, adjust=False).mean().iloc[-1]
        ema21 = hist['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
        
        # Squeeze Detection (Bollinger Band Compression)
        std_dev = hist['Close'].tail(20).std()
        upper_bb = hist['Close'].tail(20).mean() + (2 * std_dev)
        lower_bb = hist['Close'].tail(20).mean() - (2 * std_dev)
        bb_width = (upper_bb - lower_bb) / current_price
        
        # RSI 14
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))

        technical_summary = f"""
        Price: ${current_price:.2f}
        RVOL: {rvol} (Relative Volume)
        EMA 8/21: {ema8:.2f}/{ema21:.2f} ({'Bullish Crossover' if ema8 > ema21 else 'Bearish Slope'})
        Price vs SMA50/200: {'Above Key MAs' if current_price > sma50 else 'Below Resistance'}
        RSI: {rsi:.1f} ({'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral'})
        BB Width: {bb_width:.3f} ({'Squeezing' if bb_width < 0.05 else 'Expanding'})
        """
        
        direction = "up" if daily_change >= 0 else "down"
        
        prompt = f"""
        As a Senior Market Analyst, explain WHY {ticker} moved {daily_change:.2f}% ({direction}) today.
        
        TECHNICAL DATA:
        {technical_summary}
        
        RECENT HEADLINES:
        {json.dumps(headlines)}

        Explain in ONE SHORT sentence (max 18 words) combining both technicals (EMAs, Squeeze, Breakout, RVOL) AND news catalyst.
        Example: "Broke above 21-day EMA on high RVOL following positive FDA trial results."
        BE CONCISE. NO FLUFF.
        """
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Error fetching catalyst for {ticker}: {e}")
        return "Technical consolidation."

def fetch_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Get history for today and yesterday close to calculate chance
        hist = stock.history(period="5d") # Get a few days to be safe
        
        if hist.empty:
            return None
            
        current_price = float(hist['Close'].iloc[-1])
        volume = int(hist['Volume'].iloc[-1])
        
        # If today's volume is 0 (pre-market), use previous day for display, but keep track
        if volume == 0 and len(hist) >= 2:
            volume = int(hist['Volume'].iloc[-2])

        # Relative Volume (RVOL)
        full_hist = stock.history(period="20d")
        # Ensure we have enough data for a 10-day average
        if len(full_hist) > 10:
            avg_volume = full_hist['Volume'].iloc[-11:-1].mean()
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
            'relative_volume': rel_volume
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
