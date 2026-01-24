import requests
import json
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time

API_URL = os.environ['API_URL']
API_TOKEN = os.environ['API_TOKEN']
TIAK_BASE_URL = "https://tiak.com.tr"
TIAK_CEK_URL = f"{TIAK_BASE_URL}/cek.php"

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def scrape_tiak(date_str, category_code):
    log(f"Scraping category {category_code} for {date_str}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': f'{TIAK_BASE_URL}/en/charts',
        'Origin': TIAK_BASE_URL,
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = f"{date_obj.month}.{date_obj.day}.{date_obj.year}"
        
        data = {
            'date': formatted_date,
            'kisi': str(category_code)
        }
        
        log(f"Request: {TIAK_CEK_URL} with date={formatted_date}, kisi={category_code}")
        
        response = requests.post(
            TIAK_CEK_URL,
            data=data,
            headers=headers,
            timeout=30
        )
        response.encoding = 'utf-8'
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        programs = []
        
        table = soup.find('table')
        
        if not table:
            log(f"No table found in response")
            return []
        
        rows = table.find_all('tr')
        
        for row in rows[1:]:
            cols = row.find_all('td')
            
            if len(cols) >= 7:
                try:
                    rank_text = cols[0].text.strip()
                    if not rank_text or not rank_text.isdigit():
                        continue
                    
                    programs.append({
                        'rank': int(rank_text),
                        'name': cols[1].text.strip(),
                        'channel': cols[2].text.strip(),
                        'start_time': cols[3].text.strip(),
                        'end_time': cols[4].text.strip(),
                        'rating': float(cols[5].text.strip()),
                        'share': float(cols[6].text.strip())
                    })
                    
                except (ValueError, IndexError) as e:
                    continue
        
        log(f"Found {len(programs)} programs")
        return programs
        
    except Exception as e:
        log(f"Error: {e}")
        return []

def send_to_api(data):
    log(f"Sending to API...")
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_TOKEN}'
    }
    
    try:
        response = requests.post(API_URL, json=data, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        log(f"Success: {result}")
        return True
    except Exception as e:
        log(f"API Error: {e}")
        return False

def main():
    log("=" * 60)
    log("TİAK Scraper Started")
    log("=" * 60)
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    log(f"Date: {yesterday}")
    
    categories = {
        'total': scrape_tiak(yesterday, 1),
        'ab': scrape_tiak(yesterday, 2),
        'abc1': scrape_tiak(yesterday, 3)
    }
    
    time.sleep(2)
    
    payload = {
        'date': yesterday,
        'categories': categories
    }
    
    if send_to_api(payload):
        log("Completed successfully!")
        exit(0)
    else:
        log("Failed!")
        exit(1)

if __name__ == "__main__":
    main()
