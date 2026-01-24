import requests
import json
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time

API_URL = os.environ['API_URL']
API_TOKEN = os.environ['API_TOKEN']
TIAK_URL = "https://tiak.com.tr/en/charts"

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def scrape_tiak(date_str, category):
    log(f"Scraping {category} for {date_str}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        params = {
            'date': date_obj.strftime('%d/%m/%Y'),
            'category': category
        }
        
        response = requests.get(TIAK_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        programs = []
        table = soup.find('table')
        
        if table:
            rows = table.find_all('tr')[1:]
            
            for idx, row in enumerate(rows, 1):
                cols = row.find_all('td')
                
                if len(cols) >= 4:
                    programs.append({
                        'rank': idx,
                        'name': cols[0].text.strip(),
                        'channel': cols[1].text.strip(),
                        'rating': float(cols[2].text.strip()),
                        'share': float(cols[3].text.strip()),
                        'start_time': cols[4].text.strip() if len(cols) > 4 else None,
                        'end_time': cols[5].text.strip() if len(cols) > 5 else None,
                    })
        
        log(f"Found {len(programs)} programs")
        return programs
        
    except Exception as e:
        log(f"Error: {e}")
        return []

def send_to_api(data):
    log(f"Sending data to {API_URL}...")
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_TOKEN}'
    }
    
    try:
        response = requests.post(API_URL, json=data, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        log(f"API Response: {result}")
        return True
    except Exception as e:
        log(f"API Error: {e}")
        return False

def main():
    log("=" * 60)
    log("TİAK Scraper Started")
    log("=" * 60)
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    log(f"Target Date: {yesterday}")
    
    categories = {
        'total': scrape_tiak(yesterday, 'total'),
        'ab': scrape_tiak(yesterday, 'ab'),
        'abc1': scrape_tiak(yesterday, 'abc1')
    }
    
    time.sleep(2)
    
    payload = {
        'date': yesterday,
        'categories': categories
    }
    
    success = send_to_api(payload)
    
    if success:
        log("Scraping completed successfully!")
        exit(0)
    else:
        log("Scraping failed!")
        exit(1)

if __name__ == "__main__":
    main()
