import os
import json
import requests
import tweepy
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO

X_K = os.getenv('X_API_KEY')
X_S = os.getenv('X_API_SECRET')
X_T = os.getenv('X_ACCESS_TOKEN')
X_TS = os.getenv('X_ACCESS_SECRET')
T_K = os.getenv('TMDB_API_KEY')

COLOR_RED = (227, 10, 23)
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (16, 185, 129)
COLOR_GRAY = (110, 110, 110)

def get_font(size):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, "impact.ttf")
    if os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()

def draw_arrow(draw, x, y, direction, color):
    size = 15
    if direction == "up":
        coords = [(x, y - size), (x - size, y + size), (x + size, y + size)]
    else:
        coords = [(x, y + size), (x - size, y - size), (x + size, y - size)]
    draw.polygon(coords, fill=color)

def get_metadata(name):
    try:
        url = f"https://api.themoviedb.org/3/search/tv?api_key={T_K}&query={name}&language=tr-TR"
        r = requests.get(url).json()
        if r['results']:
            tid = r['results'][0]['id']
            d = requests.get(f"https://api.themoviedb.org/3/tv/{tid}?api_key={T_K}&language=tr-TR").json()
            return {
                'url': f"https://image.tmdb.org/t/p/w1280{d.get('backdrop_path')}" if d.get('backdrop_path') else None,
                's': d.get('number_of_seasons', 1),
                'e': d.get('number_of_episodes', 1)
            }
    except:
        return None
    return None

def create_card(data):
    W, H = 1200, 1550
    card = Image.new('RGB', (W, H), COLOR_WHITE)
    draw = ImageDraw.Draw(card)
    f_t, f_s, f_m, f_p, f_r, f_tr = get_font(130), get_font(85), get_font(32), get_font(30), get_font(120), get_font(38)

    draw.text((W/2, 160), data['n'].upper(), fill=COLOR_BLACK, font=f_t, anchor="mm")
    draw.text((W/2, 290), f"SEASON {data['s']} : EPISODE {data['e']}", fill=COLOR_RED, font=f_s, anchor="mm")
    draw.text((W/2, 390), f"AIRDATE: {data['d']} • NETWORK: {data['c']}".upper(), fill=COLOR_GRAY, font=f_m, anchor="mm")

    stats = [
        {'l': f"TOTAL ({data['r1'] or '-'})", 'sh': data['s1'], 'rt': data['ra1'], 'tr': data['t1']},
        {'l': f"AB ({data['r2'] or '-'})", 'sh': data['s2'], 'rt': data['ra2'], 'tr': data['t2']},
        {'l': f"ABC1 ({data['r3'] or '-'})", 'sh': data['s3'], 'rt': data['ra3'], 'tr': data['t3']}
    ]

    cw, ys = W/3, 420
    for i, st in enumerate(stats):
        xc = (cw * i) + (cw / 2)
        draw.rounded_rectangle((xc-170, ys, xc+170, ys+70), 35, COLOR_BLACK)
        draw.text((xc, ys+35), st['l'], COLOR_WHITE, f_p, "mm")
        draw.rounded_rectangle((xc-170, ys+85, xc+170, ys+155), 35, COLOR_RED)
        draw.text((xc, ys+120), f"SHARE: {st['sh'] or '0.0'}%", COLOR_WHITE, f_p, "mm")
        draw.text((xc, ys+250), str(st['rt'] or '0.0'), COLOR_RED, f_r, "mm")
        tv = float(st['tr'] or 0.0)
        tc = COLOR_GREEN if tv >= 0 else COLOR_RED
        draw_arrow(draw, xc-55, ys+340, "up" if tv >= 0 else "down", tc)
        draw.text((xc+15, ys+340), f"{abs(tv):.2f}", tc, f_tr, "mm")

    if data['u']:
        try:
            img = Image.open(BytesIO(requests.get(data['u']).content))
            img = ImageOps.fit(img, (W, 750), centering=(0.5, 0.2))
            card.paste(img, (0, H - 750))
            draw.rounded_rectangle((60, H-130, 150, H-70), 15, COLOR_RED)
            draw.text((105, H-100), "TR", COLOR_WHITE, f_p, "mm")
            draw.text((170, H-100), "OFFICIAL RATINGS", COLOR_WHITE, f_p, "lm")
        except: pass

    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, H), 100, 255)
    final = Image.new('RGBA', (W, H), (0,0,0,0))
    final.paste(card, (0,0), mask=mask)
    buf = BytesIO()
    final.save(buf, format='PNG')
    buf.seek(0)
    return buf

def run():
    path = 'data'
    if not os.path.exists(path): return
    files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.json')]
    if not files: return
    
    # الترتيب حسب وقت إنشاء الملف لضمان أخذ الأحدث
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, 'r', encoding='utf-8') as f:
        jd = json.load(f)

    # الإصلاح هنا: استخدام الكلمات المفتاحية Keyword Arguments لمنع خطأ 401
    auth = tweepy.OAuth1UserHandler(X_K, X_S, X_T, X_TS)
    api_v1 = tweepy.API(auth)
    client_v2 = tweepy.Client(
        consumer_key=X_K,
        consumer_secret=X_S,
        access_token=X_T,
        access_token_secret=X_TS
    )

    shows = [p for p in jd['programs'] if p['rank_total'] is not None]
    shows = sorted(shows, key=lambda x: x['rank_total'])[:3]

    for s in shows:
        meta = get_metadata(s['name'])
        if not meta: continue
        buf = create_card({
            'n': s['name'], 's': meta['s'], 'e': meta['e'], 'd': jd['date'], 'c': s['channel'],
            'r1': s['rank_total'], 's1': s['share_total'], 'ra1': s['rating_total'], 't1': 0.0,
            'r2': s['rank_ab'], 's2': s['share_ab'], 'ra2': s['rating_ab'], 't2': 0.0,
            'r3': s['rank_abc1'], 's3': s['share_abc1'], 'ra3': s['rating_abc1'], 't3': 0.0,
            'u': meta['url']
        })
        tmp = f"t_{s['name']}.png"
        with open(tmp, "wb") as f: f.write(buf.getbuffer())
        try:
            mid = api_v1.media_upload(tmp).media_id
            txt = f"📊 {s['name']} Ratings ({jd['date']})\n\nSeason {meta['s']} | Episode {meta['e']}\n\n#TurkishSeries #Rating #Dizi"
            client_v2.create_tweet(text=txt, media_ids=[mid])
            print(f"Posted: {s['name']}")
        except Exception as e: print(e)
        finally:
            if os.path.exists(tmp): os.remove(tmp)

if __name__ == "__main__":
    run()
