import time
from pykrx import stock
from datetime import datetime, timedelta

def test_krx_fetch():
    print("Testing pykrx fetch for all tickers on a specific date...")
    start_time = time.time()
    
    # Try fetching for last 5 business days
    dates = []
    curr = datetime.now()
    while len(dates) < 5:
        date_str = curr.strftime("%Y%m%d")
        # Just getting the closing price
        try:
            df = stock.get_market_ohlcv_by_ticker(date_str, market="ALL")
            if not df.empty:
                dates.append(date_str)
                print(f"Data fetched for {date_str}, {len(df)} tickers")
        except:
            pass
        curr -= timedelta(days=1)
        
    print(f"Time taken to fetch 5 days: {time.time() - start_time:.2f} seconds")
    
if __name__ == "__main__":
    test_krx_fetch()
