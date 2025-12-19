import sys
import os

# Add project dir to path
sys.path.append(os.getcwd())

from utils import fetch_current_price, process_screenshot, process_excel

def test_price():
    print("Testing Price Fetching...")
    ticker = "AAPL"
    price = fetch_current_price(ticker)
    print(f"Price for {ticker}: {price}")
    if price:
        print("✅ Price fetch successful")
    else:
        print("❌ Price fetch failed")

def test_excel():
    print("\nTesting Excel Parsing...")
    import pandas as pd
    df = pd.DataFrame({'Ticker': ['TSLA', 'MSFT', 'GOOGL']})
    df.to_excel('test.xlsx', index=False)
    tickers = process_excel('test.xlsx')
    print(f"Parsed tickers: {tickers}")
    if tickers == ['TSLA', 'MSFT', 'GOOGL']:
        print("✅ Excel parsing successful")
    else:
        print("❌ Excel parsing failed")
    os.remove('test.xlsx')

if __name__ == "__main__":
    test_price()
    test_excel()
