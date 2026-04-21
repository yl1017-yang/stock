import requests
from bs4 import BeautifulSoup
import re

def get_naver_financials(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'lxml')
    
    # 1. PER, PBR, DIV (Main Info)
    # These are often inside id="aside" -> .aside_invest
    try:
        per = soup.select_one('#_per').text.strip() if soup.select_one('#_per') else "N/A"
        pbr = soup.select_one('#_pbr').text.strip() if soup.select_one('#_pbr') else "N/A"
        # Dividend is sometimes harder to find, let's look for it
        dvd_tag = soup.select_one('#_dvd')
        dvd = dvd_tag.text.strip() if dvd_tag else "N/A"
        
        # If not found by ID, try looking for text labels
        if per == "N/A":
            per_label = soup.find('th', string=re.compile('PER'))
            if per_label:
                per = per_label.find_next_sibling('td').text.strip()
        
        print(f"Scraped - PER: {per}, PBR: {pbr}, DIV: {dvd}")
    except Exception as e:
        print(f"Error scraping main: {e}")
        per, pbr, dvd = "N/A", "N/A", "N/A"

    # 2. Operating Income (Profitability)
    # This is in the 'cop_analysis' table
    try:
        is_profitable = "N/A"
        # Find the table with business summary
        table = soup.select_one('.section.cop_analysis table')
        if table:
            # First row is usually Dates
            # Second row is usually '매출액'
            # Third row is usually '영업이익'
            rows = table.select('tr')
            for row in rows:
                th = row.select_one('th')
                if th and '영업이익' in th.text:
                    # Get the most recent value (usually the second or third <td> if the first is the label)
                    # Actually, Naver table has complex structure with annual/quarterly columns
                    tds = row.select('td')
                    if tds:
                        # Most recent annual is usually the 4th column (index 3)
                        # Let's take the last available annual data before the 'E' (estimate)
                        # Or just the first one that has data
                        latest_op = tds[3].text.strip().replace(',', '') # 2023.12 (A)
                        if latest_op and latest_op != '-':
                            val = float(latest_op)
                            is_profitable = "Pass (흑자)" if val > 0 else "Fail (적자)"
                            print(f"Scraped Operating Income: {val} -> {is_profitable}")
                            break
    except Exception as e:
        print(f"Error scraping profit: {e}")
        is_profitable = "Error"

    return per, pbr, dvd, is_profitable

if __name__ == "__main__":
    test_codes = ["373220", "005930", "086520"] # LG Ensol, Samsung, EcoPro
    for code in test_codes:
        print(f"\nTesting {code}...")
        get_naver_financials(code)
