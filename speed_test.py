
import os
import time
import yfinance as yf
from google import genai
import json

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def test_speed(ticker):
    print(f"--- Timing Analysis for {ticker} ---")
    start = time.time()
    
    # 1. Ticker init
    s = yf.Ticker(ticker)
    print(f"Ticker init: {time.time() - start:.2f}s")
    
    # 2. News
    t = time.time()
    news = s.news[:3]
    print(f"News fetch: {time.time() - t:.2f}s")
    
    # 3. History
    t = time.time()
    hist = s.history(period="1y")
    print(f"History fetch (1y): {time.time() - t:.2f}s")
    
    # 4. Gemini
    if client:
        t = time.time()
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents="Say hi"
        )
        print(f"Gemini call: {time.time() - t:.2f}s")
    else:
        print("Gemini client NOT found.")

    print(f"Total time: {time.time() - start:.2f}s")

if __name__ == "__main__":
    test_speed("CORT")
