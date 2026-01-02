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
        
        # Calculate Relative Volume (RVOL) - matches Thinkorswim multipliers
        # We compare today's volume to the average of the last 10 days
        full_hist = stock.history(period="15d")
        avg_volume = full_hist['Volume'].tail(11).head(10).mean() # Avg of previous 10 days
        rel_volume = round(volume / avg_volume, 2) if avg_volume > 0 else 1.0
        
        # Calculate daily change
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
        # Step 1: Try reading with Pandas (most robust method)
        df = None
        if file_path.endswith('.csv'):
            try:
                # We use on_bad_lines='skip' to handle cases where metadata rows have different column counts
                df = pd.read_csv(file_path, header=None, sep=None, engine='python', on_bad_lines='skip')
            except Exception as e:
                print(f"DEBUG: Pandas CSV read failed: {e}. Falling back to raw text scan.")
        else:
            try:
                df = pd.read_excel(file_path, header=None)
            except Exception as e:
                print(f"DEBUG: Pandas Excel read failed: {e}")

        # Step 2: If Pandas worked, use the column-based scoring logic
        if df is not None and not df.empty:
            print(f"DEBUG: DataFrame loaded. Shape: {df.shape}")
            ticker_pattern = re.compile(r'^[A-Z0-9.]{1,8}$')
            ignore_list = ['SYMBOL', 'TICKER', 'STOCK', 'PRICE', 'LAST', 'CHANGE', 'VOLUME', 'HIGH', 'LOW', 'OPEN', 'CLOSE', 'NET', 'CHG', 'DESC', '8', 'WATCH']
            column_results = []

            for col in df.columns:
                col_data = df[col].dropna().astype(str).tolist()
                valid_tickers = []
                for item in col_data:
                    clean_item = item.strip().upper()
                    clean_item = re.sub(r'^\d+\s+', '', clean_item)
                    if ticker_pattern.match(clean_item) and clean_item not in ignore_list:
                        valid_tickers.append(clean_item)
                    else:
                        matches = re.findall(r'\b[A-Z0-9.]{1,8}\b', clean_item)
                        for m in matches:
                            if m not in ignore_list and any(c.isalpha() for c in m):
                                valid_tickers.append(m)

                seen = set()
                unique_tickers = [x for x in valid_tickers if not (x in seen or seen.add(x))]
                has_keyword = any(any(kw in str(val).lower() for kw in ['symbol', 'ticker', 'stock']) for val in df[col].head(15))
                
                column_results.append({'count': len(unique_tickers), 'tickers': unique_tickers, 'has_keyword': has_keyword, 'col_index': col})

            column_results.sort(key=lambda x: (x['count'] > 2, x['has_keyword'], x['count']), reverse=True)
            if column_results and column_results[0]['count'] > 0:
                print(f"DEBUG: Selected Col {column_results[0]['col_index']} with {column_results[0]['count']} tickers")
                return column_results[0]['tickers']

        # Step 3: Foolproof Fallback (Raw Text Scan)
        # If pandas failed OR found 0 tickers, we scan the whole file for ticker-like strings
        print("DEBUG: Using Raw Text Fallback parsing...")
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Find anything that looks like a ticker: 1-6 uppercase letters surrounded by boundaries
            # We filter out known common headers manually
            raw_matches = re.findall(r'\b[A-Z]{1,6}\b', content)
            ignore_set = {'WATCHLIST', 'SYMBOL', 'DESCRIPTION', 'LAST', 'PRICE', 'CHANGE', 'VOLUME', 'HIGH', 'LOW', 'OPEN', 'CLOSE', 'NET', 'CHG'}
            tickers = []
            seen = set()
            for m in raw_matches:
                if m not in ignore_set and m not in seen:
                    tickers.append(m)
                    seen.add(m)
            print(f"DEBUG: Raw scan found {len(tickers)} potential tickers")
            return tickers
            
    except Exception as e:
        print(f"ERROR: Final catch in process_excel: {e}")
        return []
