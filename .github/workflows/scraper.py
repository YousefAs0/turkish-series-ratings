import os
import json
import requests
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def parse_table(html):
    soup = BeautifulSoup(html, 'html.parser')
    data = {}
    table = soup.find('table')
    if not table: return data
    
    rows = table.find_all('tr')[1:]
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 7: continue
        
        name = " ".join(cells[1].get_text(strip=True).split())
        if not name or name == '-': continue
        
        rank_text = cells[0].get_text(strip=True).replace('.', '')
        rating_text = cells[5].get_text(strip=True).replace(',', '.')
        share_text = cells[6].get_text(strip=True).replace(',', '.')
        
        data[name] = {
            'rank': int(rank_text) if rank_text.isdigit() else None,
            'channel': cells[2].get_text(strip=True),
            'start_time': cells[3].get_text(strip=True),
            'end_time': cells[4].get_text(strip=True),
            'rating': float(rating_text) if rating_text != '-' and rating_text != '' else None,
            'share': float(share_text) if share_text != '-' and share_text != '' else None
        }
    return data

def scrape_single_date(target_date_obj):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            target_date_tr = target_date_obj.strftime("%d.%m.%Y")
            target_date_db = target_date_obj.strftime("%Y-%m-%d")
            
            log(f"Processing Date: {target_date_tr}")

            page.goto('https://tiak.com.tr/en/charts', wait_until='networkidle', timeout=90000)
            page.wait_for_selector('#daily-tables')
            page.click('#daily-tables')
            
            page.wait_for_selector('#datepicker')
            page.fill('#datepicker', target_date_tr)
            page.keyboard.press('Enter')
            
            time.sleep(5)
            page.wait_for_load_state('networkidle')

            actual_date = page.input_value('#datepicker')
            if actual_date != target_date_tr:
                log(f"Data mismatch for {target_date_tr}, got {actual_date}")
                return None

            results = {'total': {}, 'ab': {}, 'abc1': {}}
            categories = [{'id': '1', 'key': 'total'}, {'id': '2', 'key': 'ab'}, {'id': '3', 'key': 'abc1'}]

            for cat in categories:
                old_content = page.inner_text('#tablo')
                page.select_option('#kisi', cat['id'])
                try:
                    page.wait_for_function(f"document.querySelector('#tablo').innerText !== `{old_content}`", timeout=10000)
                except:
                    pass
                
                time.sleep(2)
                html = page.inner_html('#tablo')
                results[cat['key']] = parse_table(html)

            all_names = set(list(results['total'].keys()) + list(results['ab'].keys()) + list(results['abc1'].keys()))
            final_programs = []

            for name in all_names:
                ref = results['total'].get(name) or results['ab'].get(name) or results['abc1'].get(name)
                if not ref: continue

                prog = {
                    'name': name,
                    'channel': ref['channel'],
                    'start_time': ref['start_time'],
                    'end_time': ref['end_time'],
                    'rank_total': results['total'].get(name, {}).get('rank'),
                    'rating_total': results['total'].get(name, {}).get('rating'),
                    'share_total': results['total'].get(name, {}).get('share'),
                    'rank_ab': results['ab'].get(name, {}).get('rank'),
                    'rating_ab': results['ab'].get(name, {}).get('rating'),
                    'share_ab': results['ab'].get(name, {}).get('share'),
                    'rank_abc1': results['abc1'].get(name, {}).get('rank'),
                    'rating_abc1': results['abc1'].get(name, {}).get('rating'),
                    'share_abc1': results['abc1'].get(name, {}).get('share'),
                }
                final_programs.append(prog)

            return {'date': target_date_db, 'programs': final_programs}

        except Exception as e:
            log(f"Error scraping {target_date_tr}: {str(e)}")
            return None
        finally:
            browser.close()

def main():
    try:
        today = datetime.now()
        weekday = today.weekday()
        
        target_dates = []
        
        if weekday == 5 or weekday == 6:
            log("Weekend detected. Skipping execution.")
            return

        if weekday == 0:
            target_dates = [
                today - timedelta(days=3),
                today - timedelta(days=2),
                today - timedelta(days=1)
            ]
        else:
            target_dates = [today - timedelta(days=1)]

        os.makedirs('data', exist_ok=True)
        
        for i, date_obj in enumerate(target_dates):
            data = scrape_single_date(date_obj)
            
            if data and data['programs']:
                filename = f"data/ratings_{data['date']}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                if API_URL and API_TOKEN:
                    headers = {'Authorization': f'Bearer {API_TOKEN}', 'Content-Type': 'application/json'}
                    requests.post(API_URL, json=data, headers=headers, timeout=60)
                    log(f"Data for {data['date']} pushed to API")

                if i < len(target_dates) - 1:
                    log("Waiting 30 seconds before next request...")
                    time.sleep(30)
            else:
                log(f"No data collected for {date_obj.strftime('%Y-%m-%d')}")

        log("Execution Cycle Completed")

    except Exception as e:
        log(f"Critical Execution Failed: {e}")
        exit(1)

if __name__ == '__main__':
    main()
