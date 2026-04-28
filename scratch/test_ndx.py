import pandas as pd
import requests

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers)
    tables = pd.read_html(res.text)
    
    # Usually the components table is the 4th, but let's find the one with 'Ticker'
    nasdaq_tickers = []
    for t in tables:
        if 'Ticker' in t.columns:
            nasdaq_tickers = t['Ticker'].tolist()
            break
        elif 'Symbol' in t.columns:
            nasdaq_tickers = t['Symbol'].tolist()
            break

    print(f"Found {len(nasdaq_tickers)} tickers.")
    if nasdaq_tickers:
        print(nasdaq_tickers[:10])
except Exception as e:
    print(f"Error: {e}")
