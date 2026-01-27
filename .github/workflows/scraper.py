import os
import json
import requests
import time
from datetime import datetime
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
        
        name = cells[1].get_text(strip=True)
        if not name or name == '-': continue
        
        data[name] = {
            'rank': int(cells[0].get_text(strip=True)) if cells[0].get_text(strip=True).isdigit() else 0,
            'channel': cells[2].get_text(strip=True),
            'start_time': cells[3].get_text(strip=True),
            'end_time': cells[4].get_text(strip=True),
            'rating': float(cells[5].get_text(strip=True).replace(',', '.')) if cells[5].get_text(strip=True) != '-' else 0.0,
            'share': float(cells[6].get_text(strip=True).replace(',', '.')) if cells[6].get_text(strip=True) != '-' else 0.0
        }
    return data

def scrape_tiak():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto('https://tiak.com.tr/en/charts', wait_until='networkidle', timeout=90000)
            page.wait_for_selector('#daily-tables')
            page.click('#daily-tables')
            time.sleep(5)
            
            site_date = page.input_value('#datepicker')
            day, month, year = site_date.split('.')
            db_date = f"{year}-{month}-{day}"
            log(f"Site Date: {db_date}")
            
            results = {'total': {}, 'ab': {}, 'abc1': {}}
            categories = [
                {'id': '1', 'key': 'total'},
                {'id': '2', 'key': 'ab'},
                {'id': '3', 'key': 'abc1'}
            ]

            for cat in categories:
                log(f"Category: {cat['key']}")
                page.select_option('#kisi', cat['id'])
                page.wait_for_load_state('networkidle')
                time.sleep(4)
                html = page.inner_html('#tablo')
                results[cat['key']] = parse_table(html)

            all_names = set(list(results['total'].keys()) + list(results['ab'].keys()) + list(results['abc1'].keys()))
            final_programs = []

            for name in all_names:
                ref = results['total'].get(name) or results['ab'].get(name) or results['abc1'].get(name)
                
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

            return {
                'date': db_date,
                'programs': final_programs
            }

        except Exception as e:
            log(f"Error: {str(e)}")
            raise e
        finally:
            browser.close()

def main():
    try:
        data = scrape_tiak()
        if not data['programs']:
            raise Exception("No programs found")

        os.makedirs('data', exist_ok=True)
        filename = f"data/ratings_{data['date']}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        if API_URL and API_TOKEN:
            requests.post(API_URL, json=data, headers={'Authorization': f'Bearer {API_TOKEN}'}, timeout=60)
        
        log("Success")
    except Exception:
        log("Failed")
        exit(1)

if __name__ == '__main__':
    main()
