
import os
import time
import json
from datetime import datetime

# Mock a Flask environment to test the internal logic
def full_review_test(ticker):
    print(f"\n--- STARTING COMPREHENSIVE REVIEW FOR {ticker} ---\n")
    
    # Check Imports
    tstart = time.time()
    try:
        import yfinance as yf
        from google import genai
        import pandas as pd
        print(f"[1/5] Imports confirmed: {time.time() - tstart:.2f}s")
    except Exception as e:
        print(f"FAILED: Import error: {e}")
        return

    # 1. Price Fetch Logic
    t1 = time.time()
    try:
        # Step A: Download
        hist = yf.download(ticker, period="1mo", progress=False, timeout=10)
        t_download = time.time() - t1
        print(f"      - yf.download: {t_download:.2f}s")
        
        if hist.empty:
            print(f"      - ERROR: Ticker history is empty.")
            return

        # Step B: Calculations
        current_price = float(hist['Close'].iloc[-1])
        daily_change = 0.0
        if len(hist) >= 2:
            prev_close = float(hist['Close'].iloc[-2])
            daily_change = float(((current_price - prev_close) / prev_close) * 100)
        print(f"      - Calculations complete (Price: ${current_price:.2f}, Chg: {daily_change:.2f}%)")
        print(f"[2/5] Price Fetch Logic: {time.time() - t1:.2f}s")
    except Exception as e:
        print(f"FAILED: Price fetch: {e}")
        return

    # 2. Catalyst Logic (include_news=False)
    t2 = time.time()
    try:
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
        
        if not client:
            print("      - WARNING: Gemini Client unavailable.")
        else:
            # Emulate the prompt
            technical_summary = f"Price: ${current_price:.2f}, RSI: 50.0"
            direction = "up" if daily_change >= 0 else "down"
            prompt = f"Explain why {ticker} moved {daily_change:.2f}% ({direction}). Techs: {technical_summary}. No major news found. One short sentence (max 15 words)."
            
            response = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
            print(f"      - Gemini Response: '{response.text.strip()}'")
        
        print(f"[3/5] Catalyst Logic: {time.time() - t2:.2f}s")
    except Exception as e:
        print(f"FAILED: Catalyst logic: {e}")
        return

    # 3. Overall Latency Check
    total = time.time() - tstart
    print(f"\n[SUMMARY] Total local execution: {total:.2f}s")
    if total > 5.0:
        print("CRITICAL: Local execution is too slow (>5s). This will definitely timeout on Heroku.")
    else:
        print("VERIFIED: Local core logic is fast. The issue is likely network-specific to Heroku (Rate limiting or DB).")

if __name__ == "__main__":
    full_review_test("CORT")
