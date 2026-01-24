import os
import json
import requests
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
import time

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def scrape_tiak_with_browser(date_str):
    log(f"Starting browser scraping for {date_str}")
    
    day, month, year = date_str.split('.')
    
    all_data = {
        'date': f"{year}-{month}-{day}",
        'categories': {
            'total': [],
            'ab': [],
            'abc1': []
        }
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            log("Opening TİAK charts page...")
            page.goto('https://tiak.com.tr/en/charts', wait_until='networkidle', timeout=60000)
            
            log("Waiting for page to load...")
            time.sleep(3)
            
            log("Clicking on Daily Reports...")
            page.click('#daily-tables')
            time.sleep(2)
            
            categories = [
                {'name': 'total', 'value': '1', 'label': 'All People'},
                {'name': 'ab', 'value': '2', 'label': 'AB'},
                {'name': 'abc1', 'value': '3', 'label': '20+ABC1'}
            ]
            
            for category in categories:
                try:
                    log(f"Selecting category: {category['label']}")
                    
                    page.select_option('#kisi', category['value'])
                    
                    log("Waiting for table to update...")
                    time.sleep(3)
                    
                    table_html = page.inner_html('#tablo')
                    
                    programs = parse_table_html(table_html)
                    all_data['categories'][category['name']] = programs
                    
                    log(f"Found {len(programs)} programs in {category['label']}")
                    
                except Exception as e:
                    log(f"Error scraping {category['label']}: {str(e)}")
                    all_data['categories'][category['name']] = []
            
        except Exception as e:
            log(f"Browser error: {str(e)}")
            return None
        
        finally:
            browser.close()
    
    return all_data

def parse_table_html(html):
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html, 'html.parser')
    programs = []
    
    table = soup.find('table')
    if not table:
        return programs
    
    rows = table.find_all('tr')
    
    for row in rows[1:]:
        cells = row.find_all('td')
        
        if len(cells) < 7:
            continue
        
        try:
            rank = cells[0].get_text(strip=True)
            name = cells[1].get_text(strip=True)
            channel = cells[2].get_text(strip=True)
            start_time = cells[3].get_text(strip=True)
            end_time = cells[4].get_text(strip=True)
            rating = cells[5].get_text(strip=True)
            share = cells[6].get_text(strip=True)
            
            if not name or name == '-' or not rank:
                continue
            
            program = {
                'rank': int(rank) if rank.isdigit() else 0,
                'channel': channel,
                'name': name,
                'start_time': start_time,
                'end_time': end_time,
                'rating': float(rating.replace(',', '.')) if rating and rating != '-' else 0.0,
                'share': float(share.replace(',', '.')) if share and share != '-' else 0.0
            }
            
            programs.append(program)
            
        except Exception as e:
            continue
    
    return programs

def send_to_api(data):
    log("Sending to API...")
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_TOKEN}'
    }
    
    try:
        response = requests.post(API_URL, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            log(f"Success: {result}")
            return True
        else:
            log(f"API Error {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        log(f"Request failed: {str(e)}")
        return False

def main():
    log("=" * 60)
    log("TİAK Scraper Started")
    log("=" * 60)
    
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime('%m.%d.%Y')
    
    log(f"Target date: {date_str}")
    
    data = scrape_tiak_with_browser(date_str)
    
    if not data:
        log("Failed to scrape data")
        exit(1)
    
    if not data['categories']['total']:
        log("No data found for this date")
        exit(1)
    
    log(f"Total programs scraped:")
    log(f"  - All People: {len(data['categories']['total'])}")
    log(f"  - AB: {len(data['categories']['ab'])}")
    log(f"  - ABC1: {len(data['categories']['abc1'])}")
    
    if send_to_api(data):
        log("Completed successfully!")
        exit(0)
    else:
        log("Failed to send to API")
        exit(1)

if __name__ == '__main__':
    main()
