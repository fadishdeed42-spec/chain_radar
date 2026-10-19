"""Chain Radar — finds crypto stories that are about to go viral and pings Telegram.
Runs every 15 min on GitHub Actions. Free sources only. State in state/seen.json.
Env: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (required), GEMINI_API_KEY (optional, for drafts)."""
import os, re, json, time, html, hashlib, io, sys
from datetime import datetime, timezone
import requests, feedparser

TOKEN, CHAT = os.environ.get('TELEGRAM_TOKEN', ''), os.environ.get('TELEGRAM_CHAT_ID', '')
GEMINI = os.environ.get('GEMINI_API_KEY', '')
STATE = 'state/seen.json'
NOW = time.time()
UA = {'User-Agent': 'Mozilla/5.0 (ChainRadar news scanner; +github.com/fadishdeed42-spec/chain_radar)'}
ALERT, WATCH = 65, 50          # score thresholds
FRESH_H = 6                    # only stories newer than this many hours

FEEDS = {
    'CoinDesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
    'Cointelegraph': 'https://cointelegraph.com/rss',
    'Decrypt': 'https://decrypt.co/feed',
    'The Block': 'https://www.theblock.co/rss.xml',
    'Bitcoin Magazine': 'https://bitcoinmagazine.com/.rss/full/',
    'CryptoSlate': 'https://cryptoslate.com/feed/',
    'Blockworks': 'https://blockworks.co/feed',
}
GNEWS = ['crypto hack OR exploit', 'crypto arrested OR charged OR sentenced', 'bitcoin OR ethereum price',
         'crypto exchange halts withdrawals', 'SEC crypto OR crypto ETF', 'crypto liquidations']
KEYWORDS = [  # (regex, points)
    (r'\b(hack|hacked|exploit|exploited|drained|stolen|heist|breach)\b', 25),
    (r'\b(halt|halts|halted|paused|suspend|suspends|frozen|freeze|outage|insolven|bankrupt)', 22),
    (r'\b(arrest|arrested|charged|sentenced|indicted|extradit|lawsuit|sues|sued|fraud|ponzi|scam)', 18),
    (r'\b(sec|etf|approv|ban|bans|banned|executive order|federal reserve|fed)\b', 14),
    (r'\bliquidat', 15), (r'\bbillion\b|\$\d+(\.\d+)?b\b', 15), (r'\bmillion\b|\$\d+(\.\d+)?m\b', 6),
    (r'\b(record|all-time high|ath|new high)\b', 12),
    (r'\b(crash|crashes|plunge|plunges|tumble|soar|soars|surge|surges|skyrocket|dump|collapse)', 10),
    (r'\b(trump|musk|saylor|blackrock|tesla|microstrategy|strategy inc|binance|coinbase|tether|cz|vitalik)\b', 8),
    (r'\b(whale|kidnap|murder|dead|missing|vanish)', 8),
]
STOP = set('the a an of to in on for and or is are as at by with from after over into its it this that new says said will be has have more than up down crypto'.split())


def get(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=20, **kw)
        r.raise_for_status()
        return r
    except Exception as e:
        print('fetch fail', url[:80], e)
        return None


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {'stories': {}, 'movers': {}, 'hacks': {}, 'init': False}


def save_state(s):
    os.makedirs('state', exist_ok=True)
    for k in ('stories', 'movers', 'hacks'):
        s[k] = {i: t for i, t in s[k].items() if NOW - t < 72 * 3600}
    s['menu'] = {i: m for i, m in s.get('menu', {}).items() if NOW - m['t'] < 48 * 3600}
    json.dump(s, open(STATE, 'w'), indent=0, sort_keys=True)


def words(t):
    return {w for w in re.findall(r'[a-z0-9$]+', t.lower()) if w not in STOP and len(w) > 2}


# ---------------- collect ----------------
def collect_news():
    items = []
    for src, url in FEEDS.items():
        r = get(url)
        if not r:
            continue
        for e in feedparser.parse(r.content).entries[:40]:
            ts = e.get('published_parsed') or e.get('updated_parsed')
            ts = time.mktime(ts) - time.timezone if ts else NOW
            items.append({'title': html.unescape(e.get('title', '')).strip(), 'url': e.get('link', ''), 'src': src, 'ts': ts})
    for q in GNEWS:
        r = get('https://news.google.com/rss/search', params={'q': q + ' when:1d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
        if not r:
            continue
        for e in feedparser.parse(r.content).entries[:25]:
            ts = e.get('published_parsed')
            ts = time.mktime(ts) - time.timezone if ts else NOW
            t = html.unescape(e.get('title', ''))
            src = t.rsplit(' - ', 1)[-1] if ' - ' in t else 'Google News'
            items.append({'title': t.rsplit(' - ', 1)[0].strip(), 'url': e.get('link', ''), 'src': src, 'ts': ts})
    return [i for i in items if i['title'] and NOW - i['ts'] < FRESH_H * 3600 and i['ts'] <= NOW + 600]


def collect_reddit():
    out = []
    for kind in ('rising', 'hot'):
        r = get(f'https://www.reddit.com/r/CryptoCurrency/{kind}.json', params={'limit': 30})
        if not r:
            continue
        try:
            for c in r.json()['data']['children']:
                d = c['data']
                if NOW - d.get('created_utc', 0) < 12 * 3600:
                    out.append({'title': d['title'], 'ups': d.get('ups', 0), 'comments': d.get('num_comments', 0)})
        except Exception as e:
            print('reddit parse', e)
    if not out:  # JSON API blocks cloud IPs; RSS often still works (no vote counts)
        for kind in ('rising', 'hot'):
            r = get(f'https://www.reddit.com/r/CryptoCurrency/{kind}/.rss')
            if r:
                out += [{'title': html.unescape(e.get('title', '')), 'ups': 0, 'comments': 0} for e in feedparser.parse(r.content).entries[:25]]
    return out


def collect_market():
    r = get('https://api.coingecko.com/api/v3/coins/markets', params={
        'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 100, 'page': 1, 'price_change_percentage': '1h,24h'})
    if not r:
        return []
    try:
        return [{'id': c['id'], 'sym': c['symbol'].upper(), 'name': c['name'], 'price': c['current_price'] or 0,
                 'h1': c.get('price_change_percentage_1h_in_currency') or 0,
                 'h24': c.get('price_change_percentage_24h_in_currency') or 0, 'rank': c.get('market_cap_rank') or 999}
                for c in r.json()]
    except Exception as e:
        print('market parse', e)
        return []


def collect_hacks():
    r = get('https://api.llama.fi/hacks')
    if not r:
        return []
    try:
        return [h for h in r.json() if NOW - float(h.get('date', 0)) < 36 * 3600]
    except Exception as e:
        print('hacks parse', e)
        return []


# ---------------- cluster + score ----------------
def cluster(items):
    items.sort(key=lambda i: i['ts'])
    groups = []
    for it in items:
        w = words(it['title'])
        best, bs = None, 0
        for g in groups:
            j = len(w & g['w']) / max(1, len(w | g['w']))
            if j > bs:
                best, bs = g, j
        if best and bs >= 0.34:
            best['items'].append(it); best['w'] |= w
        else:
            groups.append({'items': [it], 'w': set(w)})
    return groups


def coin_in(text, market):
    t = ' ' + text + ' '
    for c in market:
        if c['rank'] > 100:
            continue
        if re.search(r'[\s(]' + re.escape(c['name']) + r'[\s,.:\'’)]', t, re.I) or \
           (len(c['sym']) >= 3 and re.search(r'[\s($]' + re.escape(c['sym']) + r'[\s,.:)]', t)):
            return c
    return None


def score_group(g, market, reddit):
    titles = [i['title'] for i in g['items']]
    lead = max(g['items'], key=lambda i: len(words(i['title'])))
    srcs = {i['src'] for i in g['items']}
    first = min(i['ts'] for i in g['items'])
    s = min(40, 10 * len(srcs))                                         # spread across outlets
    txt = ' '.join(titles).lower()
    s += min(45, sum(p for rx, p in KEYWORDS if re.search(rx, txt)))     # drama
    coin = coin_in(lead['title'], market)
    if coin:
        if abs(coin['h24']) >= 8 or abs(coin['h1']) >= 4:
            s += 15
        if coin['sym'] in ('BTC', 'ETH') and abs(coin['h1']) >= 2:
            s += 10
    for p in reddit:                                                    # reddit echo
        if len(words(p['title']) & g['w']) >= 3:
            s += 10 if p['ups'] > 300 else 5
            break
    age_h = (NOW - first) / 3600
    if age_h > 3:
        s -= int((age_h - 3) * 8)                                       # stale
    if len(g['items']) >= 2 and NOW - first < 3600:
        s += 8                                                          # fast pile-on
    return max(0, min(100, s)), lead, coin, srcs, age_h


def key_of(g):
    return hashlib.md5(' '.join(sorted(list(g['w']))[:12]).encode()).hexdigest()[:12]


def remember(st, g, lead, coin, srcs):
    """Store a story so the owner can tap 'Make post' on it later."""
    k = key_of(g)
    st.setdefault('menu', {})[k] = {'title': lead['title'], 'url': lead['url'], 'src': lead['src'], 't': NOW,
                                    'coin': coin['id'] if coin else '', 'srcs': sorted(srcs)[:5],
                                    'urls': [i['url'] for i in g['items'] if 'news.google' not in i['url']][:4]}
    return k


# ---------------- chart ----------------
def chart(coin, label=''):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        r = get(f'https://api.coingecko.com/api/v3/coins/{coin["id"]}/market_chart', params={'vs_currency': 'usd', 'days': 1})
        if not r:
            return None
        pts = r.json()['prices']
        xs = [datetime.fromtimestamp(p[0] / 1000, timezone.utc) for p in pts]; ys = [p[1] for p in pts]
        up = ys[-1] >= ys[0]
        BG, GOLD, RED, GRN, MUT = '#0b0d12', '#d4a843', '#e5484d', '#26c2a0', '#8a93a6'
        fig = plt.figure(figsize=(10.8, 13.5), dpi=100, facecolor=BG)
        ax = fig.add_axes([0.08, 0.18, 0.86, 0.56], facecolor=BG)
        col = GRN if up else RED
        ax.plot(xs, ys, color=col, lw=4)
        ax.fill_between(xs, ys, min(ys), color=col, alpha=0.12)
        i = max(range(len(ys)), key=lambda k: abs(ys[k] - ys[0]))       # biggest move point
        ax.scatter([xs[i]], [ys[i]], s=900, facecolors='none', edgecolors=GOLD, linewidths=4, zorder=5)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(colors=MUT, labelsize=16); ax.grid(color='#1c2130', lw=1)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'${v:,.0f}' if v >= 100 else f'${v:,.4g}'))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H:%M'))
        ch = (ys[-1] / ys[0] - 1) * 100
        fig.text(0.08, 0.92, f'{coin["name"]} ({coin["sym"]})', color='white', fontsize=40, weight='bold')
        fig.text(0.08, 0.86, f'${ys[-1]:,.6g}   {ch:+.1f}% (24h)', color=col, fontsize=34, weight='bold')
        if label:
            fig.text(0.08, 0.80, label[:60], color=GOLD, fontsize=22)
        fig.text(0.08, 0.08, 'CHAIN SECRETS', color=GOLD, fontsize=26, weight='bold')
        fig.text(0.08, 0.05, 'Every chart hides a story', color=MUT, fontsize=16)
        fig.text(0.94, 0.05, f'Data: CoinGecko · {datetime.now(timezone.utc):%b %d %H:%M} UTC', color=MUT, fontsize=14, ha='right')
        buf = io.BytesIO(); fig.savefig(buf, format='png', facecolor=BG); plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print('chart fail', e)
        return None


# ---------------- drafts ----------------
def draft(headline, coin, srcs):
    base = f'⚡ {headline}'
    if coin:
        base += f'\n\n{coin["sym"]}: ${coin["price"]:,.6g} ({coin["h24"]:+.1f}% 24h)'
    if not GEMINI:
        return base
    prompt = ('Write ONE post for X (max 260 characters) for the crypto news account "Chain Secrets" (witty crypto-detective voice). '
              'Use ONLY the facts below, no new numbers, no predictions, no hashtags spam (max 1), no links. Start with a strong hook.\n'
              f'Headline(s): {headline}\nSources: {", ".join(list(srcs)[:4])}\n'
              + (f'Price: {coin["name"]} ${coin["price"]:,.6g}, {coin["h24"]:+.1f}% in 24h, {coin["h1"]:+.1f}% in 1h\n' if coin else ''))
    try:
        r = requests.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
                          params={'key': GEMINI}, json={'contents': [{'parts': [{'text': prompt}]}]}, timeout=30)
        t = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        return t[:280] if t else base
    except Exception as e:
        print('gemini fail', e)
        return base


# ---------------- telegram ----------------
def tg(text, photo=None, buttons=None):
    """buttons: list of (label, callback_data) -> inline keyboard under the message."""
    if not TOKEN or not CHAT:
        print('NO TELEGRAM:\n', text); return
    api = f'https://api.telegram.org/bot{TOKEN}/'
    kb = {}
    if buttons:
        rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
        kb = {'reply_markup': json.dumps({'inline_keyboard': [[{'text': a, 'callback_data': b} for a, b in r] for r in rows]})}
    try:
        if photo:
            short = len(text) <= 1024
            r = requests.post(api + 'sendPhoto', data={'chat_id': CHAT, 'caption': text if short else '', 'parse_mode': 'HTML',
                                                      **(kb if short else {})}, files={'photo': ('chart.png', photo)}, timeout=30)
            if r.ok and short:
                return
        requests.post(api + 'sendMessage', data={'chat_id': CHAT, 'text': text[:4000], 'parse_mode': 'HTML',
                                                  'disable_web_page_preview': 'true', **kb}, timeout=30)
    except Exception as e:
        print('telegram fail', e)


E = html.escape


def story_msg(sc, lead, coin, srcs, items, age_h, urgent):
    head = '🚨 <b>POST NOW</b>' if urgent else '📌 <b>Worth posting</b>'
    links = []
    for it in sorted(items, key=lambda i: i['ts'])[:3]:
        links.append(f'• <a href="{E(it["url"])}">{E(it["src"])}</a>')
    d = draft(lead['title'], coin, srcs)
    m = (f'{head} · score {sc}/100 · {len(srcs)} sources · {age_h*60:.0f} min old\n\n'
         f'<b>{E(lead["title"])}</b>\n\n')
    if coin:
        m += f'📈 {coin["sym"]} ${coin["price"]:,.6g} · {coin["h1"]:+.1f}% 1h · {coin["h24"]:+.1f}% 24h\n\n'
    m += f'✍️ <b>Draft (check facts, then post):</b>\n<code>{E(d)}</code>\n\n🔗 Sources:\n' + '\n'.join(links)
    return m


# ---------------- main ----------------
def main():
    st = load_state()
    first_run = not st.get('init')
    market, news, reddit, hacks = collect_market(), collect_news(), collect_reddit(), collect_hacks()
    print(f'market {len(market)} news {len(news)} reddit {len(reddit)} hacks {len(hacks)}')
    groups = cluster(news)
    scored = sorted([(score_group(g, market, reddit), g) for g in groups], key=lambda x: -x[0][0])
    sent = 0

    for (sc, lead, coin, srcs, age), g in scored[:10]:
        remember(st, g, lead, coin, srcs)
    if first_run:
        send_top(st, scored, '✅ <b>Chain Radar is live.</b> I check crypto news, prices and hacks every 15 minutes and ping you here.')
        for _, g in scored:
            st['stories'][key_of(g)] = NOW
        for h in hacks:
            st['hacks'][str(h.get('name')) + str(h.get('date'))] = NOW
        for c in market:
            if abs(c['h1']) >= 5:
                st['movers'][c['id']] = NOW
        st['init'] = True
        save_state(st); return

    # 1) hacks from DefiLlama
    for h in hacks:
        k = str(h.get('name')) + str(h.get('date'))
        amt = float(h.get('amount') or 0)
        if k in st['hacks'] or amt < 1e6:
            continue
        st['hacks'][k] = NOW
        tg(f'🚨 <b>HACK ALERT</b> · {E(str(h.get("name")))} · ${amt/1e6:,.1f}M\n'
           f'Chain: {E(str(h.get("chain") or h.get("chains") or "?"))} · Method: {E(str(h.get("technique") or h.get("classification") or "?"))}\n\n'
           f'✍️ <code>{E(draft(f"{h.get("name")} hacked for ${amt/1e6:,.1f}M ({h.get("technique") or "exploit"})", None, ["DefiLlama"]))}</code>\n\n'
           f'🔗 <a href="https://defillama.com/hacks">DefiLlama hacks</a> (verify with a news source before posting)')
        sent += 1

    # 2) big price movers
    for c in market:
        big = (c['sym'] in ('BTC', 'ETH') and abs(c['h1']) >= 2.5) or (c['rank'] <= 50 and abs(c['h1']) >= 6) or \
              (c['rank'] <= 100 and abs(c['h1']) >= 9)
        last = st['movers'].get(c['id'], 0)
        if not big or NOW - last < 6 * 3600:
            continue
        st['movers'][c['id']] = NOW
        verb = 'pumps' if c['h1'] > 0 else 'dumps'
        news_hit = next((lead for (sc, lead, coin, srcs, age), g in scored if coin and coin['id'] == c['id']), None)
        m = (f'🚨 <b>PRICE MOVE</b> · {c["name"]} {verb} {c["h1"]:+.1f}% in 1h ({c["h24"]:+.1f}% 24h) · ${c["price"]:,.6g}\n\n'
             + (f'Possible reason: <b>{E(news_hit["title"])}</b>\n<a href="{E(news_hit["url"])}">{E(news_hit["src"])}</a>\n\n' if news_hit
                else 'No news found yet. Check X search for the reason before posting.\n\n')
             + f'✍️ <code>{E(draft(f"{c["name"]} {verb} {abs(c["h1"]):.1f}% in one hour", c, ["CoinGecko"]))}</code>')
        tg(m, chart(c, f'{c["h1"]:+.1f}% in the last hour'))
        sent += 1

    # 3) news stories
    watch = []
    for (sc, lead, coin, srcs, age), g in scored:
        k = key_of(g)
        if k in st['stories']:
            continue
        if sc >= ALERT:
            st['stories'][k] = NOW
            mk = remember(st, g, lead, coin, srcs)
            tg(story_msg(sc, lead, coin, srcs, g['items'], age, True), chart(coin, lead['title']) if coin else None,
               [('📝 Make full post', 'p:' + mk)])
            sent += 1
        elif sc >= WATCH:
            st['stories'][k] = NOW
            watch.append((sc, lead, srcs, remember(st, g, lead, coin, srcs)))
    if watch:
        msg = '📌 <b>Worth a look</b> (not urgent). Tap a number to get a full post:\n'
        for n, (sc, lead, srcs, mk) in enumerate(watch[:5], 1):
            msg += f'\n<b>{n}.</b> ({sc}/100, {len(srcs)} src) <a href="{E(lead["url"])}">{E(lead["title"])}</a>'
        tg(msg, None, [(f'📝 {n}', 'p:' + w[3]) for n, w in enumerate(watch[:5], 1)])
    print('alerts sent', sent, 'watch', len(watch))
    save_state(st)


# ---------------- pick-a-story: full post ----------------
def send_top(st, scored, header='📰 <b>Top crypto stories right now</b>'):
    msg, btn = header + '\n\nTap a number and I make a full post (title, text, thread, candle chart):\n', []
    for n, ((sc, lead, coin, srcs, age), g) in enumerate(scored[:6], 1):
        k = remember(st, g, lead, coin, srcs)
        msg += f'\n<b>{n}.</b> ({sc}/100, {len(srcs)} src) {E(lead["title"])}'
        btn.append((f'📝 {n}', 'p:' + k))
    tg(msg, None, btn)


def find_coin(text):
    """Coin named in the text: top-250 by name/symbol, else CoinGecko search on $TICKER / CAPS words."""
    mk = []
    for page in (1, 2):
        r = get('https://api.coingecko.com/api/v3/coins/markets', params={'vs_currency': 'usd', 'order': 'market_cap_desc',
                'per_page': 125, 'page': page, 'price_change_percentage': '1h,24h'})
        if r:
            mk += [{'id': c['id'], 'sym': c['symbol'].upper(), 'name': c['name'], 'price': c['current_price'] or 0,
                    'h1': c.get('price_change_percentage_1h_in_currency') or 0,
                    'h24': c.get('price_change_percentage_24h_in_currency') or 0, 'rank': 1} for c in r.json()]
    c = coin_in(text, mk)
    if c:
        return c
    for tok in re.findall(r'\$?\b([A-Z]{2,6})\b', text):
        if tok in ('SEC', 'ETF', 'USD', 'CEO', 'DOJ', 'FBI', 'NFT', 'AI', 'US', 'UK', 'EU', 'IRS', 'CFTC', 'IPO', 'DAO', 'DEX'):
            continue
        r = get('https://api.coingecko.com/api/v3/search', params={'query': tok})
        hits = [x for x in (r.json().get('coins', []) if r else []) if x['symbol'].upper() == tok]
        if hits:
            q = get('https://api.coingecko.com/api/v3/simple/price', params={'ids': hits[0]['id'], 'vs_currencies': 'usd',
                    'include_24hr_change': 'true'})
            d = (q.json() if q else {}).get(hits[0]['id'], {})
            return {'id': hits[0]['id'], 'sym': tok, 'name': hits[0]['name'], 'price': d.get('usd', 0), 'h1': 0,
                    'h24': d.get('usd_24h_change') or 0, 'rank': hits[0].get('market_cap_rank') or 999}
    return None


def wrap(t, n):
    out, line = [], ''
    for w in t.split():
        if len(line) + len(w) + 1 > n:
            out.append(line); line = w
        else:
            line = (line + ' ' + w).strip()
    return out + [line] if line else out


def candle_chart(coin, title, days=1):
    """Real OHLC candles (CoinGecko) in Chain Secrets style, biggest candle circled."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        r = get(f'https://api.coingecko.com/api/v3/coins/{coin["id"]}/ohlc', params={'vs_currency': 'usd', 'days': days})
        rows = r.json() if r else []
        if len(rows) < 8:
            return None
        BG, GOLD, RED, GRN, MUT = '#0b0d12', '#d4a843', '#e5484d', '#26c2a0', '#8a93a6'
        fig = plt.figure(figsize=(10.8, 13.5), dpi=100, facecolor=BG)
        ax = fig.add_axes([0.09, 0.16, 0.85, 0.52], facecolor=BG)
        w = 0.62
        for i, (t, o, h, l, c) in enumerate(rows):
            col = GRN if c >= o else RED
            ax.plot([i, i], [l, h], color=col, lw=2)
            ax.add_patch(Rectangle((i - w / 2, min(o, c)), w, max(abs(c - o), (h - l) * 0.02 or 1e-9), color=col))
        big = max(range(len(rows)), key=lambda i: abs(rows[i][4] - rows[i][1]))
        ax.scatter([big], [(rows[big][2] + rows[big][3]) / 2], s=2600, facecolors='none', edgecolors=GOLD, linewidths=4, zorder=5)
        ax.set_xlim(-1, len(rows)); ax.set_ylim(min(x[3] for x in rows) * 0.997, max(x[2] for x in rows) * 1.003)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(colors=MUT, labelsize=15); ax.grid(color='#1c2130', lw=1)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'${v:,.0f}' if v >= 100 else f'${v:,.4g}'))
        step = max(1, len(rows) // 6)
        ax.set_xticks(range(0, len(rows), step))
        ax.set_xticklabels([datetime.fromtimestamp(rows[i][0] / 1000, timezone.utc).strftime('%H:%M' if days <= 1 else '%b %d')
                            for i in range(0, len(rows), step)])
        first, last = rows[0][1], rows[-1][4]; ch = (last / first - 1) * 100; col = GRN if ch >= 0 else RED
        y = 0.94
        for ln in wrap(title, 34)[:3]:
            fig.text(0.07, y, ln, color='white', fontsize=34, weight='bold'); y -= 0.045
        fig.text(0.07, y - 0.02, f'{coin["name"]} ({coin["sym"]})  ${last:,.6g}  {ch:+.1f}% ({"24h" if days <= 1 else f"{days}d"})',
                 color=col, fontsize=26, weight='bold')
        fig.text(0.07, 0.07, 'CHAIN SECRETS', color=GOLD, fontsize=26, weight='bold')
        fig.text(0.07, 0.045, 'Every chart hides a story', color=MUT, fontsize=16)
        fig.text(0.95, 0.045, f'Data: CoinGecko · {"30m" if days <= 1 else "4h"} candles · {datetime.now(timezone.utc):%b %d %H:%M} UTC',
                 color=MUT, fontsize=13, ha='right')
        buf = io.BytesIO(); fig.savefig(buf, format='png', facecolor=BG); plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print('candle fail', e)
        return None


def title_card(title, src):
    """Branded headline image for stories with no coin to chart."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        BG, GOLD, MUT = '#0b0d12', '#d4a843', '#8a93a6'
        fig = plt.figure(figsize=(10.8, 13.5), dpi=100, facecolor=BG)
        fig.text(0.08, 0.86, 'BREAKING', color='#e5484d', fontsize=30, weight='bold')
        y = 0.76
        for ln in wrap(title, 22)[:7]:
            fig.text(0.08, y, ln, color='white', fontsize=52, weight='bold'); y -= 0.075
        fig.text(0.08, 0.10, 'CHAIN SECRETS', color=GOLD, fontsize=30, weight='bold')
        fig.text(0.08, 0.07, f'Source: {src}', color=MUT, fontsize=18)
        buf = io.BytesIO(); fig.savefig(buf, format='png', facecolor=BG); plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print('card fail', e)
        return None


def article_text(urls):
    for u in urls:
        r = get(u)
        if not r or 'html' not in r.headers.get('content-type', ''):
            continue
        t = re.sub(r'(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>', ' ', r.text)
        paras = [html.unescape(re.sub(r'<[^>]+>', '', p)).strip() for p in re.findall(r'(?is)<p[^>]*>(.*?)</p>', t)]
        paras = [p for p in paras if len(p) > 60]
        if paras:
            return ' '.join(paras)[:6000]
    return ''


def gemini(prompt):
    if not GEMINI:
        return ''
    for model in ('gemini-flash-latest', 'gemini-2.5-flash', 'gemini-2.0-flash'):
        try:
            r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                              params={'key': GEMINI}, timeout=60,
                              json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.7}})
            if r.ok:
                return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            print('gemini', model, r.status_code)
        except Exception as e:
            print('gemini fail', model, e)
    return ''


def make_post(item):
    coin = find_coin(item['title'])
    body = article_text(item.get('urls') or [item['url']])
    facts = (f'Headline: {item["title"]}\nSources: {", ".join(item.get("srcs") or [item["src"]])}\n'
             + (f'Price now: {coin["name"]} ({coin["sym"]}) ${coin["price"]:,.6g}, {coin["h24"]:+.1f}% in 24h\n' if coin else '')
             + (f'Article text:\n{body}\n' if body else ''))
    out = gemini('You write for the X account "Chain Secrets": crypto news with the chart that proves it, witty crypto-detective voice.\n'
                 'Using ONLY the facts below (no invented numbers, quotes or claims; say "reportedly" if the source is unsure; '
                 'no price predictions; no links; max 1 hashtag), reply in exactly this format:\n'
                 'TITLE: <a punchy full title, max 70 chars>\n'
                 'POST: <one X post, max 270 chars, strong hook first line, key number, why it matters>\n'
                 'THREAD:\n1/ ...\n2/ ...\n3/ ...\n4/ ... (4 posts, each max 270 chars, story beats + twist + lesson)\n'
                 'REPLY: <one short reply idea to post under big news accounts>\n\n' + facts)
    if not out:
        out = (f'TITLE: {item["title"]}\nPOST: ⚡ {item["title"]}'
               + (f'\n\n{coin["sym"]}: ${coin["price"]:,.6g} ({coin["h24"]:+.1f}% 24h)' if coin else '')
               + '\n\n(Add a Gemini key to get a written post + thread here.)')
    img = None
    if coin:
        img = candle_chart(coin, item['title'], 1) or candle_chart(coin, item['title'], 7)
    if not img:
        img = title_card(item['title'], item['src'])
    m = re.search(r'TITLE:\s*(.+)', out)
    cap = f'🖼 <b>{E(m.group(1).strip() if m else item["title"])}</b>\n' + (f'Chart: {coin["name"]} real candles' if coin else 'Headline card (no coin to chart)')
    tg(cap, img)
    tg(f'✍️ <b>Ready to post</b> (check the facts first):\n\n<code>{E(out)}</code>\n\n🔗 <a href="{E(item["url"])}">{E(item["src"])}</a>')


def listen():
    """Handle button taps and messages: tap 📝 → full post; send /top → current list; send a link → post about it."""
    st = load_state()
    off = st.get('tg_offset', 0)
    r = get(f'https://api.telegram.org/bot{TOKEN}/getUpdates', params={'offset': off + 1, 'timeout': 0})
    ups = (r.json().get('result', []) if r else [])
    print('updates', len(ups))
    for u in ups:
        st['tg_offset'] = max(st.get('tg_offset', 0), u['update_id'])
        cb, msg = u.get('callback_query'), u.get('message')
        who = str((cb or msg or {}).get('from', {}).get('id', '')) if (cb or msg) else ''
        if who and CHAT and who != str(CHAT):
            continue                                   # only obey the owner
        if cb:
            try:
                requests.post(f'https://api.telegram.org/bot{TOKEN}/answerCallbackQuery', data={'callback_query_id': cb['id'],
                              'text': 'Making your post…'}, timeout=10)
            except Exception:
                pass
            k = (cb.get('data') or '')[2:]
            item = st.get('menu', {}).get(k)
            if item:
                tg(f'⏳ Making a full post about:\n<b>{E(item["title"])}</b>')
                make_post(item)
            else:
                tg('That story expired. Send /top for the current list.')
        elif msg and msg.get('text'):
            t = msg['text'].strip()
            if t.lower().startswith('/top') or t.lower() in ('top', 'list', 'news'):
                market, news = collect_market(), collect_news()
                scored = sorted([(score_group(g, market, []), g) for g in cluster(news)], key=lambda x: -x[0][0])
                send_top(st, scored)
            elif re.match(r'https?://', t):
                tg('⏳ Making a full post from your link…')
                pg = get(t); ttl = re.search(r'(?is)<title[^>]*>(.*?)</title>', pg.text) if pg else None
                ttl = html.unescape(ttl.group(1)).split(' | ')[0].split(' - ')[0].strip() if ttl else t
                make_post({'title': ttl, 'url': t, 'src': re.sub(r'^https?://(www\.)?([^/]+).*', r'\2', t), 'urls': [t]})
            else:
                tg('Send <b>/top</b> for today\'s top stories, tap a 📝 button, or paste a news link.')
    save_state(st)


if __name__ == '__main__':
    mode = sys.argv[1] if sys.argv[1:] else 'scan'
    if mode == 'listen':
        listen()
    elif mode == 'top':
        st = load_state(); m, n = collect_market(), collect_news()
        send_top(st, sorted([(score_group(g, m, []), g) for g in cluster(n)], key=lambda x: -x[0][0])); save_state(st)
    else:
        main()
