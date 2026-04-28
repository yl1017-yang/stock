import yfinance as yf
import pandas as pd

def test_yf():
    # Get subset of S&P500
    print("Fetching SP500")
    try:
        tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        sp500_df = tables[0]
        tickers = sp500_df['Symbol'].tolist()[:5] # Test with 5
        print("Got tickers:", tickers)
        
        for t in tickers:
            ticker = yf.Ticker(t)
            info = ticker.info
            mc = info.get('marketCap', 0)
            pe = info.get('trailingPE', 0)
            pb = info.get('priceToBook', 0)
            print(f"{t}: MC={mc}, PE={pe}, PB={pb}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_yf()
