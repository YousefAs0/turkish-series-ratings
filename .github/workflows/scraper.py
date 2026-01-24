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
        'scraped_at': datetime.now().isoformat(),
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

def merge_categories(data):
    log("Merging categories...")
    
    merged = []
    
    for total_program in data['categories']['total']:
        program_name = total_program['name']
        
        ab_program = next(
            (p for p in data['categories']['ab'] if p['name'] == program_name),
            None
        )
        
        abc1_program = next(
            (p for p in data['categories']['abc1'] if p['name'] == program_name),
            None
        )
        
        merged_program = {
            'name': total_program['name'],
            'channel': total_program['channel'],
            'start_time': total_program['start_time'],
            'end_time': total_program['end_time'],
            'rank_total': total_program['rank'],
            'rating_total': total_program['rating'],
            'share_total': total_program['share'],
            'rank_ab': ab_program['rank'] if ab_program else None,
            'rating_ab': ab_program['rating'] if ab_program else None,
            'share_ab': ab_program['share'] if ab_program else None,
            'rank_abc1': abc1_program['rank'] if abc1_program else None,
            'rating_abc1': abc1_program['rating'] if abc1_program else None,
            'share_abc1': abc1_program['share'] if abc1_program else None,
        }
        
        merged.append(merged_program)
    
    log(f"Merged {len(merged)} programs")
    
    return {
        'date': data['date'],
        'scraped_at': data['scraped_at'],
        'programs': merged
    }

def save_data_to_file(data, date_str, suffix=''):
    log(f"Saving data to file{' (' + suffix + ')' if suffix else ''}...")
    
    os.makedirs('data', exist_ok=True)
    
    filename = f"data/ratings_{date_str.replace('.', '-')}{('_' + suffix) if suffix else ''}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"✓ Data saved to {filename}")
        return filename
    except Exception as e:
        log(f"✗ Failed to save file: {str(e)}")
        return None

def commit_to_github(filename, date_str):
    log("Committing to GitHub...")
    
    try:
        os.system('git config --global user.email "github-actions[bot]@users.noreply.github.com"')
        os.system('git config --global user.name "GitHub Actions Bot"')
        os.system(f'git add {filename}')
        commit_message = f"Add TİAK ratings for {date_str}"
        os.system(f'git commit -m "{commit_message}"')
        os.system('git push')
        log("✓ Successfully committed to GitHub")
        return True
    except Exception as e:
        log(f"✗ Git commit failed: {str(e)}")
        return False

def send_to_api(data):
    log("Attempting to send to API...")
    
    log("=== DATA STRUCTURE ===")
    log(json.dumps(data, indent=2, ensure_ascii=False))
    log("=== END DATA ===")
    
    if not API_URL or not API_TOKEN:
        log("⚠️ API credentials not configured, skipping API call")
        return False
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_TOKEN}'
    }
    
    try:
        response = requests.post(API_URL, json=data, headers=headers, timeout=30)
        log(f"API Response Status: {response.status_code}")
        log(f"API Response Body: {response.text[:500]}")
        
        if response.status_code == 200:
            result = response.json()
            log(f"✓ API Success: {result}")
            return True
        else:
            log(f"✗ API Error {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log(f"✗ API Request failed: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return False

def main():
    log("=" * 60)
    log("TİAK Scraper Started")
    log("=" * 60)
    
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime('%d.%m.%Y')
    
    log(f"Target date: {date_str}")
    
    data = scrape_tiak_with_browser(date_str)
    
    if not data:
        log("✗ Failed to scrape data")
        exit(1)
    
    if not data['categories']['total']:
        log("✗ No data found for this date")
        exit(1)
    
    log(f"✓ Total programs scraped:")
    log(f"  - All People: {len(data['categories']['total'])}")
    log(f"  - AB: {len(data['categories']['ab'])}")
    log(f"  - ABC1: {len(data['categories']['abc1'])}")
    
    filename_raw = save_data_to_file(data, date_str, 'raw')
    
    merged_data = merge_categories(data)
    
    filename = save_data_to_file(merged_data, date_str)
    
    if not filename:
        log("✗ Failed to save data locally")
        exit(1)
    
    git_success = commit_to_github(filename, date_str)
    
    api_success = send_to_api(merged_data)
    
    log("=" * 60)
    log("SUMMARY")
    log("=" * 60)
    log(f"✓ Data Scraped: YES")
    log(f"✓ Saved Locally: {'YES' if filename else 'NO'}")
    log(f"✓ Committed to GitHub: {'YES' if git_success else 'NO'}")
    log(f"✓ Sent to API: {'YES' if api_success else 'NO'}")
    
    if git_success:
        log("✓ SUCCESS: Data saved in GitHub!")
        exit(0)
    else:
        log("✗ FAILED: Could not save data")
        exit(1)

if __name__ == '__main__':
    main()
