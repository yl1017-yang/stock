import os
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
import dart_fss as dart

load_dotenv()

def test_pykrx():
    print("--- Pykrx Test ---")
    # Try to find a valid date
    for i in range(10):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        df = stock.get_market_fundamental_by_ticker(date, market="ALL")
        if not df.empty:
            print(f"Found data for {date}")
            print("Columns:", df.columns.tolist())
            print("Index sample:", df.index.tolist()[:5])
            sample_ticker = df.index[0]
            print(f"Sample row for {sample_ticker}:\n", df.loc[sample_ticker])
            break
    else:
        print("No bulk data found in last 10 days")

    # Test individual fetch
    print("\nIndividual fetch test:")
    ticker = "005930" # Samsung Electronics
    indiv_df = stock.get_market_fundamental(date, date, ticker)
    if not indiv_df.empty:
        print(f"Individual data for {ticker}:\n", indiv_df.iloc[-1])
        print("Columns:", indiv_df.columns.tolist())
    else:
        print(f"No individual data for {ticker}")

def test_dart():
    print("\n--- DART Test ---")
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("DART_API_KEY not found in .env")
        return
    
    dart.set_api_key(api_key=api_key)
    corp_list = dart.get_corp_list()
    ticker = "005930" # Samsung
    corp = corp_list.find_by_stock_code(ticker)
    if corp:
        print(f"Found corp: {corp.corp_name}")
        fs = corp.extract_fs(bgn_de='20230101')
        if 'is' in fs:
            df = fs['is']
            print("Income Statement Columns:", df.columns.tolist())
            print("Income Statement first 5 rows:\n", df[['account_nm', 'concept_id']].head())
            
            # Find operating income
            op_row = df[df['account_nm'].str.contains('영업이익|영업손실', na=False)]
            if not op_row.empty:
                print("Operating Income Row Found:")
                print(op_row.iloc[0])
            else:
                print("Operating Income Row NOT found")
        else:
            print("Income Statement not found in fs")
    else:
        print(f"Corp not found for {ticker}")

if __name__ == "__main__":
    test_pykrx()
    # test_dart() # Commented out by default to avoid using API key if not set, but I can check if it exists
    if os.getenv('DART_API_KEY'):
        test_dart()
