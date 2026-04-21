import os
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
import sys

# Try to load .env from different possible locations
load_dotenv()
load_dotenv('e:/프로젝트모음/00_git/stock/.env')

def test_pykrx():
    print("--- Pykrx Test ---")
    
    # Try different dates
    dates_to_try = [
        datetime.now().strftime('%Y%m%d'),
        (datetime.now() - timedelta(days=1)).strftime('%Y%m%d'),
        (datetime.now() - timedelta(days=2)).strftime('%Y%m%d'),
        (datetime.now() - timedelta(days=5)).strftime('%Y%m%d'),
        "20260417", # A known date from data.json
    ]
    
    for date in dates_to_try:
        print(f"\nTrying date: {date}")
        try:
            df = stock.get_market_fundamental_by_ticker(date, market="ALL")
            if df.empty:
                print(f"Result for {date} is EMPTY")
            else:
                print(f"Successfully fetched data for {date}")
                print(f"Shape: {df.shape}")
                print("Columns:", df.columns.tolist())
                print("First 3 rows:\n", df.head(3))
                # Check for PER, PBR, DIV specifically
                for col in ['PER', 'PBR', 'DIV', '배당수익률']:
                    if col in df.columns:
                        print(f"Column '{col}' found. Sample values: {df[col].head(3).tolist()}")
                    else:
                        print(f"Column '{col}' NOT FOUND")
                break
        except Exception as e:
            print(f"Error for {date}: {type(e).__name__}: {e}")

def test_dart_config():
    print("\n--- DART Config Test ---")
    api_key = os.getenv('DART_API_KEY')
    print(f"DART_API_KEY: {'[HIDDEN]' if api_key else 'NOT FOUND'}")
    if api_key:
        print(f"API Key Length: {len(api_key)}")
    
    # Check if .env file exists and its content (safely)
    env_path = 'e:/프로젝트모음/00_git/stock/.env'
    if os.path.exists(env_path):
        print(f".env file exists at {env_path}")
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if 'DART_API_KEY' in line:
                    print(f"Found DART_API_KEY in .env: {line.split('=')[0]} = ...")
    else:
        print(f".env file NOT FOUND at {env_path}")

if __name__ == "__main__":
    test_pykrx()
    test_dart_config()
