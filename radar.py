"""Chain Radar — finds crypto stories that are about to go viral and pings Telegram.
Runs every 15 min on GitHub Actions. Free sources only. State in state/seen.json.
Env: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (required), GEMINI_API_KEY (optional, for drafts)."""
import os, re, json, time, html, hashlib, io, sys, glob
from datetime import datetime, timezone, timedelta
import requests, feedparser
import brain
import replies
import shorts

TOKEN, CHAT = os.environ.get('TELEGRAM_TOKEN', ''), os.environ.get('TELEGRAM_CHAT_ID', '')
GEMINI = os.environ.get('GEMINI_API_KEY', '')
STATE = 'state/seen.json'
NOW = time.time()
UA = {'User-Agent': 'Mozilla/5.0 (ChainRadar news scanner; +github.com/fadishdeed42-spec/chain_radar)'}
ALERT, WATCH = 70, 50          # score thresholds
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


def get(url, timeout=12, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=timeout, **kw)
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
        s[k] = {i: t for i, t in s.get(k, {}).items() if NOW - t < 72 * 3600}
    s['menu'] = {i: m for i, m in s.get('menu', {}).items() if NOW - m['t'] < 48 * 3600}
    json.dump(s, open(STATE, 'w'), indent=0, sort_keys=True)


def words(t):
    return {w for w in re.findall(r'[a-z0-9$]+', t.lower()) if w not in STOP and len(w) > 2}


# ---------------- collect ----------------
def collect_news():
    """All feeds fetched in parallel (~3-5 s total)."""
    from concurrent.futures import ThreadPoolExecutor
    jobs = [('feed', src, url, None) for src, url in FEEDS.items()] + \
           [('g', None, 'https://news.google.com/rss/search', {'q': q + ' when:1d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'}) for q in GNEWS]

    def one(job):
        kind, src, url, params = job
        r = get(url, timeout=10, params=params)
        out = []
        if not r:
            return out
        for e in feedparser.parse(r.content).entries[:40]:
            ts = e.get('published_parsed') or e.get('updated_parsed')
            ts = time.mktime(ts) - time.timezone if ts else NOW
            t = html.unescape(e.get('title', '')).strip()
            if kind == 'g':
                s2 = t.rsplit(' - ', 1)[-1] if ' - ' in t else 'Google News'
                t = t.rsplit(' - ', 1)[0].strip()
            else:
                s2 = src
            out.append({'title': t, 'url': e.get('link', ''), 'src': s2, 'ts': ts})
        return out
    with ThreadPoolExecutor(16) as ex:
        items = [i for lst in ex.map(one, jobs) for i in lst]
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
    merged = []                                                          # 2nd pass: same story, different wording
    for g in groups:
        sg = story_sig(max(g['items'], key=lambda i: len(i['title']))['title'])
        for m in merged:
            if same_story(sg, m['sig']):
                m['items'] += g['items']; m['w'] |= g['w']; break
        else:
            g['sig'] = sg; merged.append(g)
    return merged


def same_story(a, b):
    aw, bw = set(a['w']), set(b['w']); inter = len(aw & bw)
    if inter / max(1, len(aw | bw)) >= 0.3 or inter >= 4:
        return True
    return bool(set(a['e']) & set(b['e']) and set(a['k']) & set(b['k']) and inter >= 2)


AMBIG = {'near', 'flow', 'pi', 'gas', 'sun', 'pump', 'core', 'story', 'movement', 'mantle', 'sonic', 'stacks', 'render', 'kaspa',
         'injective', 'tron', 'sei', 'sui', 'ondo', 'aave', 'maker', 'sky', 'hype', 'bonk', 'jupiter', 'celestia', 'arbitrum', 'optimism',
         'polygon', 'cronos', 'theta', 'the graph', 'gala', 'immutable', 'beam', 'ronin', 'pyth', 'worldcoin', 'virtual', 'ethena',
         'bitget token', 'leo', 'dai', 'usds', 'world liberty financial', 'official trump', 'gate', 'dexe', 'jito', 'raydium', 'quant'}


def coin_in(text, market):
    t = ' ' + text + ' '
    for c in market:
        if c['rank'] > 100:
            continue
        if c['name'].lower() in AMBIG and not re.search(r'[\s($]' + re.escape(c['sym']) + r'[\s,.:)]', t):
            continue
        if re.search(r'[\s(]' + re.escape(c['name']) + r'[\s,.:\'’)]', t) or \
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
    first = min(g['items'], key=lambda i: i.get('ts', 0))
    return hashlib.md5((first.get('url') or first['title']).encode()).hexdigest()[:12]


def remember(st, g, lead, coin, srcs):
    """Store a story so the owner can tap 'Make post' on it later."""
    k = key_of(g)
    st.setdefault('menu', {})[k] = {'title': lead['title'], 'url': lead['url'], 'src': lead['src'], 't': NOW,
                                    't0': min(i.get('ts', NOW) for i in g['items']),
                                    'coin': coin['id'] if coin else '', 'srcs': sorted(srcs)[:5],
                                    'urls': [i['url'] for i in g['items'] if 'news.google' not in i['url'] and not i.get('tg')][:4],
                                    'tgtext': '\n'.join(i['text'] for i in g['items'] if i.get('tg'))[:2500]}
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
    base = f'⚡ {headline}' + (f'\n\n{coin["sym"]}: {fmt_p(coin["price"])} ({coin["h24"]:+.1f}% 24h)' if coin else '')
    out = gemini(STYLE + 'Write ONE X post (max 260 characters) with a strong hook. Reply with the post text only.\n\nFACTS:\n'
                 f'Headline: {headline}\nSources: {", ".join(list(srcs)[:4])}\n'
                 + (f'Price: {coin["name"]} {fmt_p(coin["price"])}, {coin["h24"]:+.1f}% in 24h, {coin["h1"]:+.1f}% in 1h\n' if coin else ''))
    return out[:280] if out else base


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


def story_msg(sc, lead, coin, srcs, items, age_h, urgent, pr=None):
    m = (f'🔥 <b>BREAKING</b> · {age_h*60:.0f} min ago\n<b>{E(lead["title"])}</b>\n'
         f'{confirmed(srcs)} · {chance_txt(pr, sc)}')
    if coin:
        m += f'\n{coin["sym"]} {fmt_p(coin["price"])} · {coin["h1"]:+.1f}% 1h · {coin["h24"]:+.1f}% 24h'
    m += '\n' + ' · '.join(f'<a href="{E(it["url"])}">{E(it["src"])}</a>' for it in sorted(items, key=lambda i: i['ts'])[:3])
    return m


# ---------------- main ----------------
# ---------------- duplicate guard ----------------
DUP_KIND = {'hack': r'hack|exploit|drain|stole|steal|attack|breach', 'legal': r'arrest|charge|sentenc|lawsuit|sues|sued|court|indict|guilty',
            'etf': r'\betf', 'list': r'listing|lists|delist', 'outage': r'outage|halt|freez|frozen|paus|suspend', 'ban': r'\bban|seiz',
            'record': r'record|all-time high|\bath\b', 'crash': r'crash|plung|tumbl|dump|liquidat'}
COMMON = set('bitcoin btc ethereum eth crypto cryptocurrency market price traders investors sec etf etfs cftc doj fbi defi nft dao ceo usd usdt usdc '
             'breaking report new why how what this the after us'.split())


def story_sig(title):
    w = words(title)
    ents = {x.lower() for x in re.findall(r"\b[A-Z][A-Za-z0-9]{2,}\b", title)} - COMMON - STOP
    kinds = [k for k, rx in DUP_KIND.items() if re.search(rx, title.lower())]
    return {'w': sorted(w), 'e': sorted(ents), 'k': kinds}


def is_dup(st, title, urls=(), hours=36):
    """True if this story (or a near copy from another outlet) was already sent."""
    s = story_sig(title); w = set(s['w'])
    for x in st.get('sent', []):
        if NOW - x['t'] > hours * 3600:
            continue
        if set(urls) & set(x.get('u', [])):
            return True
        if same_story(s, x):
            return True
    return False


def mark_sent(st, title, urls=()):
    s = story_sig(title); s.update({'t': NOW, 'u': [u for u in urls if u][:6]})
    st['sent'] = [x for x in st.get('sent', []) if NOW - x['t'] < 48 * 3600][-150:] + [s]


MAX_PER_SCAN, MAX_PER_DAY = 2, 14
CH_NAMES = {'WatcherGuru': 'Watcher.Guru', 'wublockchainenglish': 'Wu Blockchain', 'cointelegraph': 'Cointelegraph', 'coindesk': 'CoinDesk',
            'lookonchainchannel': 'Lookonchain', 'bitcoinmagazinetelegram': 'Bitcoin Magazine', 'TheBlockNews': 'The Block',
            'decryptmedia': 'Decrypt', 'binance_announcements': 'Binance', 'PeckShieldAlert': 'PeckShield', 'tree_news_feed': 'Tree News',
            'crypto_headlines': 'Crypto Headlines'}


JUNK_RX = re.compile(r'highlight clip|^clip:|\bclip\b.*:|podcast|interview|livestream|\bama\b|giveaway|webinar|newsletter|'
                     r'price prediction|could reach|weekly recap|market wrap|sponsored|press release', re.I)
CRYPTO_RX = re.compile(r'crypto|bitcoin|btc|ethereum|\beth\b|solana|stablecoin|token|coin|blockchain|defi|exchange|binance|coinbase|'
                       r'etf|sec\b|cftc|wallet|hack|exploit|nft|web3|mining|miner|tether|usdc|xrp|memecoin|altcoin|on-chain|onchain|dex\b|'
                       r'saylor|strategy|blackrock|kraken|okx|bybit|bitfinex|kucoin|htx|huobi|gemini|robinhood|ftx|mt\.? gox|bitget|'
                       r'withdrawal|staking|airdrop|halving|satoshi|sats\b|ordinals|layer.?2|validator|ledger|metamask|\$[a-z]{2,6}\b', re.I)
CRYPTO_OUTLETS = {'CoinDesk', 'Cointelegraph', 'Decrypt', 'The Block', 'Bitcoin Magazine', 'CryptoSlate', 'Blockworks', 'Wu Blockchain',
                  'Lookonchain', 'Binance', 'The Defiant', 'DL News', 'CryptoNews', 'Crypto Briefing', 'BeInCrypto', 'U.Today', 'CoinGape'}


def junk_story(title, items, coin):
    """Not worth an alert: clips/promos, non-crypto news, tiny memecoins, or small single-wallet trades."""
    t = ' '.join(i['title'] for i in items[:4])
    if JUNK_RX.search(title):
        return True
    if not coin and not CRYPTO_RX.search(t) and not ({i.get('src') for i in items} & CRYPTO_OUTLETS):
        return True                                                      # e.g. tankers, oil, general politics
    if re.search(r'market cap|mcap|\bpump\.?fun\b', t, re.I) and re.search(r'\$\d+(\.\d+)?\s?k\b', t, re.I):
        return True                                                      # memecoins worth a few $K
    m = re.findall(r'\$(\d+(?:\.\d+)?)\s?([kmb])\b', t.lower())
    if re.search(r'\b(sold|bought|dumping|deposited|withdrew|moved|transferred|swapped)\b', t, re.I) and m and len({i['src'] for i in items}) < 2:
        biggest = max(float(v) * {'k': 1e3, 'm': 1e6, 'b': 1e9}[u] for v, u in m)
        if biggest < 20e6:
            return True                                                  # single-wallet trades under $20M from one channel
    return False


from zoneinfo import ZoneInfo
BEIRUT = ZoneInfo('Asia/Beirut')                                         # follows Lebanon's summer/winter clock changes


def quiet(now=None):
    """1:00-9:00 Beirut time: only huge news gets through."""
    h = datetime.fromtimestamp(now or time.time(), BEIRUT).hour
    return 1 <= h < 9


def confirmed(srcs):
    return f'✅ Confirmed · {len(srcs)} sources' if len(srcs) >= 2 else '⚠️ Unconfirmed · 1 source'


def chance_txt(p, sc):
    return f'🔥 Viral chance {p * 100:.0f}%' if p is not None else f'Score {sc}/100'


def fb_buttons(mk):
    return [('📝 Make post', 'p:' + mk), ('👍', f'f:{mk}:1'), ('👎', f'f:{mk}:0')]


def budget_ok(st):
    st['log'] = [t for t in st.get('log', []) if NOW - t < 86400]
    return len(st['log']) < MAX_PER_DAY


def recent_move(rows, secs):
    """Move over the last `secs` from real candles: (pct, price_then, price_now)."""
    t_end = rows[-1][0]
    i = next((j for j, r in enumerate(rows) if r[0] >= t_end - secs * 1000 + 1), 0)
    p0 = rows[i][1]
    return rows[-1][4] / p0 - 1, p0, rows[-1][4]


def main():
    st = load_state()
    first_run = not st.get('init')
    try:
        muted = json.load(open('state/tg.json')).get('mute_until', 0) > NOW
    except Exception:
        muted = False
    market, news, reddit, hacks = collect_market(), collect_news(), collect_reddit(), collect_hacks()
    for it in brain.collect_channels(NOW):
        it['src'] = CH_NAMES.get(it['src'], it['src']); news.append(it)
    print(f'market {len(market)} news {len(news)} reddit {len(reddit)} hacks {len(hacks)}')
    groups = cluster(news)
    scored = sorted([(score_group(g, market, reddit), g) for g in groups], key=lambda x: -x[0][0])
    sent = 0
    for (sc, lead, coin, srcs, age), g in scored[:40]:                  # the brain logs every notable story
        brain.log_story(key_of(g), g, sc, lead, coin, srcs, NOW)
    print('labeled', brain.label_due(NOW))
    probs = {key_of(g): brain.chance(brain.early_story(g, sc, lead, coin, srcs, NOW)) for (sc, lead, coin, srcs, age), g in scored[:40]}
    st['probs'] = {k: round(v, 3) for k, v in probs.items() if v is not None}
    brain.save()

    st['top'] = []
    if brain.model().get('ready'):
        scored.sort(key=lambda x: -(brain.chance(brain.early_story(x[1], *x[0][:4], NOW)) or 0))
    for (sc, lead, coin, srcs, age), g in scored[:10]:
        st['top'].append([remember(st, g, lead, coin, srcs), sc, round(age * 60), len(srcs)])
    st['top_at'] = NOW
    if not first_run and 'sent' not in st:          # upgrade from the old format: treat everything current as already sent
        for (sc, lead, coin, srcs, age), g in scored:
            mark_sent(st, lead['title'], [i['url'] for i in g['items']])
        save_state(st); print('migrated sent list'); return
    if first_run:
        send_top(st, scored, '✅ <b>Chain Radar is live.</b> I only ping you for big news. Send /top anytime.')
        for (sc, lead, coin, srcs, age), g in scored:
            mark_sent(st, lead['title'], [i['url'] for i in g['items']])
        for h in hacks:
            st['hacks'][str(h.get('name')) + str(h.get('date'))] = NOW
        for c in market:
            if abs(c['h1']) >= 5:
                st['movers'][c['id']] = NOW
        st['init'] = True
        save_state(st); return

    hush = quiet(NOW)

    def can_send(huge=False):
        return not muted and (huge or not hush) and sent < MAX_PER_SCAN and budget_ok(st)

    def count():
        nonlocal sent
        sent += 1; st.setdefault('log', []).append(NOW)

    # 1) hacks from DefiLlama (always worth it)
    for h in hacks:
        k = str(h.get('name')) + str(h.get('date'))
        amt = float(h.get('amount') or 0)
        if k in st['hacks'] or amt < 1e6:
            continue
        st['hacks'][k] = NOW
        title = f'{h.get("name")} hacked for ${amt/1e6:,.1f} million'
        if is_dup(st, title) or not can_send(amt >= 20e6):
            mark_sent(st, title); continue
        mark_sent(st, title)
        when = datetime.fromtimestamp(float(h.get('date', NOW)), timezone.utc).strftime('%b %d')
        hk = hashlib.md5(k.encode()).hexdigest()[:12]
        hitem = {'t': NOW, 'title': title, 'url': '', 'src': 'DefiLlama', 'tag': 'HACK',
                 'hack': {'amount': card.big_money(f'${amt:,.0f}'), 'chain': str(h.get('chain') or (h.get('chains') or [''])[0] or ''),
                          'method': str(h.get('technique') or h.get('classification') or '')[:28], 'date': when},
                 'facts': f'Hack date: {when}. Chain: {h.get("chain") or h.get("chains")}. Method: {h.get("technique") or h.get("classification")}. Amount: ${amt:,.0f}. (DefiLlama hacks database.)'}
        st.setdefault('menu', {})[hk] = hitem
        tg(f'🚨 <b>HACK</b> · <b>{E(title)}</b>\n<i>DefiLlama · verify with a news source before posting</i>', None, fb_buttons(hk))
        count()

    # 2) big price movers: only real, confirmed moves (CoinGecko and the candles must agree)
    for c in sorted(market, key=lambda c: -abs(c['h1'])):
        major = c['sym'] in ('BTC', 'ETH')
        big = (major and abs(c['h1']) >= 2.5) or (c['rank'] <= 50 and abs(c['h1']) >= 7) or (c['rank'] <= 100 and abs(c['h1']) >= 10)
        huge = (major and abs(c['h1']) >= 4) or (c['rank'] <= 20 and abs(c['h1']) >= 12)
        if not big or NOW - st['movers'].get(c['id'], 0) < (4 if major else 12) * 3600 or not can_send(huge):
            continue
        st['movers'][c['id']] = NOW
        rows, src, lab = candles(c, '8h')
        if not rows:
            continue
        mv, p0, p1 = recent_move(rows, 3600)
        if mv * c['h1'] <= 0 or abs(mv) < abs(c['h1']) * 0.5:               # sources disagree: not reliable, stay quiet
            print('mover skipped, candles disagree', c['sym'], c['h1'], round(mv * 100, 2)); continue
        verb = 'pumps' if mv > 0 else 'dumps'
        title = f'{c["name"]} {verb} {abs(mv) * 100:.1f}% in one hour'
        news_hit = next(((lead, g) for (sc, lead, coin, srcs, age), g in scored if coin and coin['id'] == c['id']), None)
        try:
            img, _ = card.chart_card(title, c, rows, lab, 'PRICE ALERT', src, focus=3600)
        except Exception as e:
            print('mover card fail', repr(e)); continue
        mk = remember(st, {'items': [{'title': title, 'url': '', 'src': 'CoinGecko', 'ts': NOW}], 'w': {c['id'], 'move', verb}},
                      {'title': title, 'url': news_hit[0]['url'] if news_hit else '', 'src': news_hit[0]['src'] if news_hit else src}, c, {src})
        st['menu'][mk].update({'chart': True, 'focus': 3600, 'span': '8h', 'tag': 'PRICE ALERT'})
        cap = f'⚡ <b>{E(title)}</b> · {fmt_p(p1)}'
        if news_hit:
            cap += f'\nLikely why: <a href="{E(news_hit[0]["url"])}">{E(news_hit[0]["title"])}</a>'
            mark_sent(st, news_hit[0]['title'], [i['url'] for i in news_hit[1]['items']])
        else:
            cap += '\n<i>No news found yet — check X for the reason.</i>'
        tg(cap, img, fb_buttons(mk))
        count()

    # 3) breaking news: only strong, real crypto stories never sent before (any outlet)
    for (sc, lead, coin, srcs, age), g in scored:
        pr = probs.get(key_of(g))
        if junk_story(lead['title'], g['items'], coin):
            continue
        tgv = max([brain.view_ratio(i['url'], NOW, early=True) for i in g['items'] if i.get('tg')] or [0])
        spreading = (len(srcs) >= 4 and age < 1.5) or (len(srcs) >= 3 and age < 1.0) or (tgv >= 2.5 and len(srcs) >= 2 and age < 1.5)
        strong = (sc >= ALERT and (pr is None or pr >= 0.25)) or (pr is not None and pr >= 0.75) or (spreading and sc >= 50)
        if not strong:
            continue
        urls = [i['url'] for i in g['items']]
        if is_dup(st, lead['title'], urls):
            continue
        mark_sent(st, lead['title'], urls)
        viral = spreading or sc >= VIRAL or (pr is not None and pr >= 0.85)          # early warning: it's spreading before the big pages post
        huge = (pr is not None and pr >= 0.9) or sc >= 92
        if not can_send(huge):
            continue
        if viral and len(srcs) >= 2:
            viral_alert(st, sc, lead, coin, srcs, g, age, pr)
        else:
            mk = remember(st, g, lead, coin, srcs)
            tg(story_msg(sc, lead, coin, srcs, g['items'], age, True, pr), None, fb_buttons(mk))
        brain.mark(lead['title'], 'alerted', 1, NOW)
        count()
    brain.save()
    print('alerts sent', sent)
    save_state(st)


def fmt_p(v):
    return card.fmt(v)


def live_top(tgs):
    m, n = collect_market(), collect_news()
    for it in brain.collect_channels(time.time()):
        it['src'] = CH_NAMES.get(it['src'], it['src']); n.append(it)
    if not n:
        tg('News sources are slow right now, try again in a minute.'); return
    st = load_state()
    scored = sorted([(score_group(g, m, []), g) for g in cluster(n)], key=lambda x: -x[0][0])
    send_top(st, scored, '📰 <b>Top crypto stories · live</b>')
    save_state(st)


# ---------------- pick-a-story: full post ----------------
import card
TG_STATE = 'state/tg.json'


def load_tg():
    try:
        return json.load(open(TG_STATE))
    except Exception:
        return {'offset': 0, 'menu': {}, 'mute_until': 0, 'story_i': 0}


def save_tg(t):
    os.makedirs('state', exist_ok=True)
    t['menu'] = {k: m for k, m in t.get('menu', {}).items() if NOW - m.get('t', NOW) < 48 * 3600}
    json.dump(t, open(TG_STATE, 'w'), indent=0, sort_keys=True)


_last_sync = [0]


def git_sync(force=False):
    """Save our state and pull the scanner's latest stories (at most once a minute unless forced)."""
    import subprocess
    if not force and time.time() - _last_sync[0] < 60:
        return
    _last_sync[0] = time.time()
    sh = lambda c: subprocess.run(c, shell=True, capture_output=True, text=True, timeout=60)
    sh('git config user.name chain-radar; git config user.email noreply@github.com')
    sh('for f in state/tg.json state/seen.json state/listen.log state/brain.json state/model.json state/shorts.json state/studio.json; do [ -f $f ] && git add $f; done; '
       '[ -d jobs ] && git add jobs; git commit -qm "listen state [skip ci]"')
    for _ in range(3):
        r = sh('git pull --rebase -q -X theirs && git push -q')
        if r.returncode == 0:
            break
        time.sleep(2)


def send_cached_top():
    git_sync()
    st = load_state(); top = st.get('top') or []
    if not top:
        return False
    mins = int((NOW_() - st.get('top_at', 0)) / 60)
    msg, btn = f'📰 <b>Top crypto stories</b> <i>(scanned {mins} min ago)</i>\nTap a number → full post with image.\n', []
    pr = st.get('probs', {})
    for n, (k, sc, age, ns) in enumerate(top[:8], 1):
        it = st.get('menu', {}).get(k)
        if not it:
            continue
        p = pr.get(k)
        tag = f'🔥 {p * 100:.0f}%' if p is not None and p >= 0.6 else f'{p * 100:.0f}%' if p is not None else ('🔥' if sc >= ALERT else '•')
        msg += f'\n<b>{n}.</b> {tag} {E(it["title"])}  <i>({"✅" if ns >= 2 else "⚠️"} {ns} src)</i>'
        btn.append((f'📝 {n}', 'p:' + k))
    btn.append(('🔄 Live refresh', 'r:'))
    tg(msg, None, btn)
    return True


def NOW_():
    return time.time()


def menu_item(k, tgs):
    if k in tgs.get('menu', {}):
        return tgs['menu'][k]
    it = load_state().get('menu', {}).get(k)
    if not it:
        git_sync(force=True); it = load_state().get('menu', {}).get(k)
    return it


def send_top(st, scored, header='📰 <b>Top crypto stories right now</b>'):
    msg, btn = header + '\nTap a number → image + post text, ready to post.\n', []
    for n, ((sc, lead, coin, srcs, age), g) in enumerate(scored[:8], 1):
        k = remember(st, g, lead, coin, srcs)
        fire = '🔥' if sc >= ALERT else '•'
        msg += f'\n<b>{n}.</b> {fire} {E(lead["title"])}  <i>({"✅" if len(srcs) >= 2 else "⚠️"} {len(srcs)} src, {age*60:.0f}m)</i>'
        btn.append((f'📝 {n}', 'p:' + k))
    tg(msg, None, btn)


NOT_CRYPTO = re.compile(r'tokeni[sz]ed|robinhood|xstock|\bstock\b|backed |ondo .*token|\binc\b|\bcorp|\betf\b|wrapped|bridged|'
                        r'wormhole|\(.*\)|\bclass [ab]\b|holdings|trust', re.I)


def cg_search(sym, strict=True):
    """Real cryptocurrency for a ticker. Never tokenized stocks / wrapped copies; strict = only coins with a real market-cap rank."""
    r = get('https://api.coingecko.com/api/v3/search', params={'query': sym})
    hits = [x for x in (r.json().get('coins', []) if r else []) if x['symbol'].upper() == sym.upper() and not NOT_CRYPTO.search(x.get('name', ''))]
    if strict:
        hits = [x for x in hits if (x.get('market_cap_rank') or 99999) <= 500]
    hits.sort(key=lambda x: x.get('market_cap_rank') or 99999)
    return hits[0] if hits else None


def coin_by_id(cid):
    r = get('https://api.coingecko.com/api/v3/coins/markets', params={'vs_currency': 'usd', 'ids': cid, 'price_change_percentage': '1h,24h'})
    c = (r.json() if r else [None])[0] if r and r.json() else None
    if not c:
        return None
    return {'id': c['id'], 'sym': c['symbol'].upper(), 'name': c['name'], 'price': c['current_price'] or 0,
            'h1': c.get('price_change_percentage_1h_in_currency') or 0, 'h24': c.get('price_change_percentage_24h_in_currency') or 0,
            'rank': c.get('market_cap_rank') or 999}


def find_coin(text):
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
        if tok in ('SEC', 'ETF', 'USD', 'CEO', 'DOJ', 'FBI', 'NFT', 'AI', 'US', 'UK', 'EU', 'IRS', 'CFTC', 'IPO', 'DAO', 'DEX', 'ETFS', 'OTC'):
            continue
        h = cg_search(tok)
        if h:
            return coin_by_id(h['id'])
    return None


SPANS = {'8h': (300, 96, 1, '8h · 5m candles'), '1d': (900, 96, 1, '24h · 15m candles'), '7d': (3600, 168, 7, '7d · 1h candles'),
         '30d': (21600, 120, 30, '30d · 6h candles'), '1y': (86400, 300, 365, '1y · daily candles')}
GRAN_LABEL = {300: '5m', 900: '15m', 3600: '1h', 21600: '6h', 86400: 'daily'}


def coinbase(sym, gran, start=None, end=None):
    params = {'granularity': gran}
    if start:
        params['start'] = datetime.fromtimestamp(start, timezone.utc).isoformat()
        params['end'] = datetime.fromtimestamp(end or time.time(), timezone.utc).isoformat()
    r = get(f'https://api.exchange.coinbase.com/products/{sym}-USD/candles', params=params, timeout=10)
    try:
        return [(t * 1000, o, h, l, c, v) for t, l, h, o, c, v in (r.json() if r else [])][::-1]
    except Exception:
        return []


_CC = {}


def candles(coin, span='1d', event_ts=None):
    k = (coin['id'], span, int(event_ts or 0))
    if k in _CC and time.time() - _CC[k][0] < 90:
        return _CC[k][1]
    out = _candles(coin, span, event_ts)
    _CC[k] = (time.time(), out)
    return out


BN_INT = {300: '5m', 900: '15m', 3600: '1h', 21600: '6h', 86400: '1d'}


def binance(sym, gran, start=None, end=None, limit=500):
    """Real Binance spot candles (public market-data mirror, works from GitHub's servers)."""
    p = {'symbol': sym.upper() + 'USDT', 'interval': BN_INT[gran], 'limit': limit}
    if start:
        p.update({'startTime': int(start * 1000), 'endTime': int((end or time.time()) * 1000)})
    r = get('https://data-api.binance.vision/api/v3/klines', params=p, timeout=10)
    try:
        return [(k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7])) for k in (r.json() if r else [])]
    except Exception:
        return []


def _candles(coin, span='1d', event_ts=None):
    """Real OHLCV. With event_ts the window is built around the news (some time before, everything after).
    Coinbase first (has volume, checked against CoinGecko price), CoinGecko OHLC fallback. Returns (rows, source, label)."""
    now = time.time()
    if event_ts and 0 < now - event_ts < 120 * 86400:
        age = now - event_ts
        total = max(age * 1.6, 3 * 3600)
        gran = next(g for g in (300, 900, 3600, 21600, 86400) if total / g <= 95 or g == 86400)
        start = max(event_ts - max(total - age, 4 * gran), now - 290 * gran)
        rows, src = binance(coin['sym'], gran, start, now), 'Binance'
        if not rows or (coin.get('price') and abs(rows[-1][4] / coin['price'] - 1) >= 0.15):
            rows, src = coinbase(coin['sym'], gran, start, now), 'Coinbase'
        lab = f'{GRAN_LABEL[gran]} candles · around the news'
        n_days = 1 if total <= 86400 else 7 if total <= 7 * 86400 else 30 if total <= 30 * 86400 else 90
    else:
        gran, n, n_days, lab = SPANS[span]
        rows, src = binance(coin['sym'], gran, limit=n), 'Binance'
        if len(rows) < 20 or (coin.get('price') and abs(rows[-1][4] / coin['price'] - 1) >= 0.15):
            rows, src = coinbase(coin['sym'], gran)[-n:], 'Coinbase'
        start = 0
    if len(rows) >= 20 and (not coin.get('price') or abs(rows[-1][4] / coin['price'] - 1) < 0.15):
        return rows, src, lab
    if not coin.get('id'):
        return [], '', ''
    r = get(f'https://api.coingecko.com/api/v3/coins/{coin["id"]}/ohlc', params={'vs_currency': 'usd', 'days': n_days})
    try:
        rows = [(t, o, h, l, c, None) for t, o, h, l, c in (r.json() if r else []) if t / 1000 >= start]
    except Exception:
        rows = []
    if len(rows) < 8:
        return [], '', ''
    gap = sorted(rows[i + 1][0] - rows[i][0] for i in range(len(rows) - 1))[len(rows) // 2] / 1000
    real = '30m' if gap < 3600 else '4h' if gap < 86400 else 'daily'
    base = (lab if event_ts else SPANS[span][3]).split(' · ')
    return rows, 'CoinGecko', f'{base[0]} · {real} candles' if not event_ts else f'{real} candles · around the news'


def coin_card(coin, title, span='1d', tag='BREAKING', col=None, note=None, event_ts=None, strict=False, focus=None):
    """Candle card. strict=True (news posts): return None when the chart doesn't actually show a move worth showing."""
    if focus:
        event_ts = None
    rows, src, lab = candles(coin, span, event_ts)
    if not rows and not event_ts and span == '1d':
        rows, src, lab = candles(coin, '7d')
    if not rows:
        return None
    try:
        img, mv = card.chart_card(title, coin, rows, lab, tag, src, int(event_ts * 1000) if event_ts else None, focus=focus)
        if strict and abs(mv) < 0.02:
            print('chart skipped: move too small', round(mv * 100, 2))
            return None
        tl = title.lower()                                    # never show a chart that contradicts the headline
        says_up = re.search(r'pump|surg|soar|rall|jump|spike|rise|rises|climb|gain|rebound|record high|ath\b|rockets|moon', tl)
        says_dn = re.search(r'dump|crash|plung|drop|fall|fell|tumbl|slid|sink|sank|tank|bleed|slump|dip|lose|loss', tl)
        if (says_up and not says_dn and mv < 0) or (says_dn and not says_up and mv > 0):
            print('chart skipped: contradicts headline', title, round(mv * 100, 2))
            return None
        return img
    except Exception as e:
        print('card fail', repr(e))
        return None


def _article(u):
    r = get(u, timeout=6)
    if not r or 'html' not in r.headers.get('content-type', ''):
        return ''
    t = re.sub(r'(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>', ' ', r.text)
    paras = [html.unescape(re.sub(r'<[^>]+>', '', p)).strip() for p in re.findall(r'(?is)<p[^>]*>(.*?)</p>', t)]
    paras = [p for p in paras if len(p) > 60]
    return ' '.join(paras)[:6000] if paras else ''


def article_text(urls):
    urls = [u for u in urls if u][:2]
    if not urls:
        return ''
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(_article, urls))
    return next((x for x in res if x), '')


_MODELS = []


def gemini_models():
    """Ask Google which models this key can use; prefer fast 'flash' models, newest first."""
    if _MODELS:
        return _MODELS
    try:
        r = requests.get('https://generativelanguage.googleapis.com/v1beta/models', params={'key': GEMINI, 'pageSize': 200}, timeout=20)
        ms = [m['name'].split('/')[-1] for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        ms = [m for m in ms if ('gemini' in m or 'gemma' in m) and not re.search(r'embed|tts|image|live|audio|vision|robot|omni', m)]
        ver = lambda n: -float((re.findall(r'(\d+(?:\.\d+)?)', n) or ['0'])[0])
        flash = sorted([m for m in ms if 'flash' in m and 'lite' not in m and 'preview' not in m and 'exp' not in m], key=ver)[:2]
        lite = sorted([m for m in ms if 'flash-lite' in m and 'preview' not in m], key=ver)[:2]
        gemma = sorted([m for m in ms if 'gemma' in m and re.search(r'27b|12b', m)], key=ver)[:2]
        other = sorted([m for m in ms if 'preview' in m and 'flash' in m], key=ver)[:1]
        mix = [x for pair in zip(lite + [None] * 2, flash + [None] * 2) for x in pair if x]   # lite first: fast & less overloaded
        _MODELS.extend(dict.fromkeys(mix + gemma + other))
    except Exception as e:
        print('model list fail', e)
    if not _MODELS:
        _MODELS.extend(['gemini-flash-latest', 'gemini-flash-lite-latest'])
    print('gemini models', _MODELS)
    return _MODELS


_NOTHINK = {}


def think_cfg(model):
    if _NOTHINK.get(model) is False:
        return {}
    if re.search(r'gemini-2\.5', model):
        return {'thinkingConfig': {'thinkingBudget': 0}}
    if re.search(r'gemini-3', model):
        return {'thinkingConfig': {'thinkingLevel': 'minimal'}}
    return {}


def gemini(prompt, timeout=20):
    if not GEMINI:
        return ''
    for attempt in range(2):
        for model in gemini_models():
            for tc in ([think_cfg(model), {}] if think_cfg(model) else [{}]):
                try:
                    r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                                      params={'key': GEMINI}, timeout=timeout,
                                      json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.7, **tc}})
                    if r.ok:
                        parts = r.json()['candidates'][0]['content']['parts']
                        return ''.join(p.get('text', '') for p in parts if not p.get('thought')).strip()
                    print('gemini', model, r.status_code, r.text[:90].replace('\n', ' '))
                    if r.status_code == 400 and tc:
                        _NOTHINK[model] = False; continue            # model doesn't accept the setting: retry plain
                    break
                except Exception as e:
                    print('gemini fail', model, e); break
        time.sleep(2)
    return ''


STYLE = ('You write for the X account "Chain Secrets": crypto news and true crypto stories with the chart that proves it, '
         'in a sharp, witty crypto-detective voice. Rules: use ONLY the facts given (never invent numbers, names, quotes or claims; '
         'say "reportedly" when the source is unsure), no price predictions, no financial advice, no links, max 1 hashtag, no emojis spam. '
         'Never use slang like bro, fam, ser, wagmi, ngmi, lfg, degen, rekt, lol. No em dashes.\n')
FORMAT = ('Reply in exactly this format and nothing else:\n'
          'TITLE: <punchy image headline, max 60 characters, include the key number if there is one>\n'
          'KEYFACT: <one short factual sentence, max 110 characters>\n'
          'TAG: <one of BREAKING, HACK, ARREST, LAWSUIT, COURT, REGULATION, ETF, MARKET, SCAM, WHALE, MYSTERY, TRUE STORY>\n'
          'VISUAL: <choose the image that best tells THIS story: CHART only if the story is about the price move or market of one '
          'specific coin/token; STAT if one striking number defines it; TIMELINE if it is a sequence of events over time; '
          'VERSUS if it is a contrast (promised vs delivered, before vs after); QUOTE only if the facts contain an exact quote; '
          'ALERT for hacks, exploits, outages or frozen withdrawals>\n'
          'SYMBOL: <ticker of the coin to chart, or NONE>\n'
          'STAT: <big value, max 10 chars, e.g. $15M or 11,196 YRS> | <label, max 30 chars>\n'
          '(Always fill STAT, TIMELINE and VERSUS when the facts allow it, even if VISUAL is something else; otherwise write NONE.)\n'
          'TIMELINE: <date> = <event, max 60 chars> ; <date> = <event> ; <date> = <event> (3-4 steps, last = the twist)\n'
          'VERSUS: <left label> = <left value> || <right label> = <right value>  (values max 18 chars)\n'
          'QUOTE: <exact quote copied word for word from the facts> = <speaker>   (or NONE)\n'
          'POST: <one X post, max 270 characters: hook line, what happened, key number, why it matters>\n'
          'REPLY: <one short reply to post under big crypto news accounts>\n')


def parse_out(out):
    g = lambda k: (re.search(r'(?m)^' + k + r':\s*(.+)', out) or [None, ''])[1].strip()
    thread = (re.search(r'THREAD:\s*(.+?)(?:\n(?:REPLY|SHORT):|\Z)', out, re.S) or [None, ''])[1].strip()
    return {'title': g('TITLE'), 'keyfact': g('KEYFACT'), 'tag': g('TAG').upper(), 'visual': g('VISUAL').upper().split()[0] if g('VISUAL') else '',
            'symbol': g('SYMBOL').upper().strip('$ '), 'stat': g('STAT'), 'timeline': g('TIMELINE'), 'versus': g('VERSUS'),
            'quote': g('QUOTE'), 'post': g('POST'), 'thread': thread, 'reply': g('REPLY'), 'short': g('SHORT')}


def options(p, item, coin):
    """Which designs this story can be shown as (for the 🎨 switch buttons)."""
    o = []
    if coin:
        o.append(('📈 Chart', 'CHART'))
    if p.get('stat') and '|' in p['stat'] and 'NONE' not in p['stat'].upper() or card.big_money(p.get('title', '') + ' ' + item.get('title', '')):
        o.append(('💰 Number', 'STAT'))
    if len([x for x in p.get('timeline', '').split(';') if '=' in x]) >= 3:
        o.append(('🕒 Timeline', 'TIMELINE'))
    if '||' in p.get('versus', '') and 'NONE' not in p['versus'].upper():
        o.append(('⚔️ Versus', 'VERSUS'))
    if '=' in p.get('quote', '') and 'NONE' not in p['quote'].upper():
        o.append(('💬 Quote', 'QUOTE'))
    o.append(('📰 Headline', 'HEADLINE'))
    return o


def build_image(p, item, facts, coin_hint=None, force=None):
    """Pick the visual that fits the story; every branch is validated so we never show a misleading chart."""
    tag = p.get('tag') or item.get('tag') or 'BREAKING'
    title, src, kf = p['title'], item.get('src') or 'Chain Secrets', p.get('keyfact', '')
    vis = force or p.get('visual', '')
    card.FOOTER_LEFT = p.get('reply') or ''
    if vis == 'HEADLINE':
        return card.headline_card(title, src, kf, tag)
    if vis == 'STAT' and not (p.get('stat') and '|' in p['stat']):
        bm = card.big_money(title + ' ' + item.get('title', ''))
        if bm:
            return card.stat_card(title, bm, 'at the center of this story', kf, tag, src)
    low = facts.lower()
    try:
        if item.get('hack') and not force:
            h = item['hack']
            return card.alert_card(title, h.get('amount', ''), [('Chain', h.get('chain', '')), ('Method', h.get('method', '')), ('Date', h.get('date', ''))],
                                   'HACKED', src)
        if vis == 'CHART' or (coin_hint and not force):
            coin = coin_hint
            if not coin and p.get('symbol') not in ('', 'NONE') and re.search(r'\b' + re.escape(p['symbol']) + r'\b', facts, re.I):
                h = cg_search(p['symbol']); coin = coin_by_id(h['id']) if h else None
            if coin:
                img = coin_card(coin, title, item.get('span') or '1d', tag if tag != 'BREAKING' else 'MARKET', event_ts=item.get('t0'),
                                strict=not force and not item.get('chart'), focus=item.get('focus'))
                if img:
                    return img
        if vis == 'ALERT':
            amt = card.big_money(title + ' ' + kf + ' ' + item.get('title', ''))
            word = 'FROZEN' if re.search(r'halt|frozen|freeze|paus|suspend', low) else 'OUTAGE' if 'outage' in low else 'EXPLOITED' if 'exploit' in low else 'HACKED'
            return card.alert_card(title, amt, [], word, src, 'HACK' if word in ('HACKED', 'EXPLOITED') else 'BREAKING')
        if vis == 'QUOTE' and '=' in p.get('quote', '') and 'NONE' not in p['quote'].upper():
            q, who = [x.strip() for x in p['quote'].rsplit('=', 1)]
            core = re.sub(r'[^a-z0-9 ]', '', q.lower())[:60]
            if core and core in re.sub(r'[^a-z0-9 ]', '', low):        # only quotes that really appear in the source
                return card.quote_card(title, q, who, tag, src)
        if vis == 'TIMELINE' and p.get('timeline'):
            steps = [tuple(x.strip() for x in st.split('=', 1)) for st in p['timeline'].split(';') if '=' in st]
            if len(steps) >= 3:
                return card.timeline_card(title, steps, tag, src)
        if vis == 'VERSUS' and '||' in p.get('versus', ''):
            l, r = [x.split('=', 1) for x in p['versus'].split('||')]
            if len(l) == 2 and len(r) == 2:
                return card.versus_card(title, (l[0].strip(), l[1].strip()), (r[0].strip(), r[1].strip()), kf, tag, src)
        if p.get('stat') and '|' in p['stat']:
            v, lab = [x.strip() for x in p['stat'].split('|', 1)]
            if v and len(v) <= 12:
                return card.stat_card(title, v, lab, kf, tag, src)
        bm = card.big_money(title + ' ' + item.get('title', ''))
        if bm:
            return card.stat_card(title, bm, 'at the center of this story', kf, tag, src)
    except Exception as e:
        print('visual fail', vis, e)
    return card.headline_card(title, src, kf, tag)


TGS = {}   # listener state, set in listen()


def caption(p, url='', src='', note=''):
    c = f'<code>{E(p["post"])}</code>'
    if url:
        c += f'\n\n🔗 <a href="{E(url)}">{E(src or "source")}</a> · check facts before posting'
    return (note + '\n\n' if note else '') + c


def post_buttons(k, p, item, coin):
    b = [(a, f'v:{k}:{v}') for a, v in options(p, item, coin)]
    extra = [('🧵 Thread', f'x:{k}:thread')]
    extra += [('💬 Reply idea', f'x:{k}:reply')] if p.get('reply') else []
    extra += [('🎬 Shorts script', f'x:{k}:short')] if item.get('story') else []
    return b + extra + [('✅ Posted', f'ps:{k}')]


def chat_action(a='upload_photo'):
    try:
        requests.post(f'https://api.telegram.org/bot{TOKEN}/sendChatAction', data={'chat_id': CHAT, 'action': a}, timeout=5)
    except Exception:
        pass


def edit_photo(msg_id, photo, text, buttons):
    """Swap the image of an existing message in place (design switch) instead of sending a new one."""
    kb = {'inline_keyboard': [[{'text': a, 'callback_data': b} for a, b in buttons[i:i + 3]] for i in range(0, len(buttons), 3)]}
    try:
        r = requests.post(f'https://api.telegram.org/bot{TOKEN}/editMessageMedia', timeout=30, files={'photo': ('card.png', photo)},
                          data={'chat_id': CHAT, 'message_id': msg_id, 'reply_markup': json.dumps(kb),
                                'media': json.dumps({'type': 'photo', 'media': 'attach://photo', 'caption': text[:1024], 'parse_mode': 'HTML'})})
        return r.ok
    except Exception:
        return False


EXTRA_PROMPT = {
    'thread': 'Write an X thread of 4-5 posts about this, each under 270 characters, numbered 1/ 2/ 3/ ... Post 1 is the hook '
              '(it goes with the image), the last post is the lesson. Reply with the thread only.',
    'short': 'Write a 40-second voiceover script for a YouTube Short about this, max 110 words, hook in the first sentence, '
             'loop-back last line. Reply with the script only.'}


def send_extra(k, what):
    d = TGS.get('designs', {}).get(k)
    if not d:
        tg('That post is too old. Make it again from /top.'); return
    p = d['p']
    if what == 'reply' and p.get('reply'):
        tg(f'💬 <b>Reply idea</b> (post under big accounts covering this)\n<code>{E(p["reply"])}</code>'); return
    if what not in EXTRA_PROMPT:
        return
    if not p.get(what):
        chat_action('typing')
        p[what] = gemini(STYLE + EXTRA_PROMPT[what] + '\n\nFACTS:\n' + d['facts'] + f'\n\nThe main post already written:\n{p["post"]}')
    if not p.get(what):
        tg('⚠️ The AI writer is busy, tap again in a minute.'); return
    head = '🧵 <b>Thread</b> (post 1 = the image post)' if what == 'thread' else '🎬 <b>Shorts script</b> (~40s)'
    tg(f'{head}\n<code>{E(p[what])}</code>')


_ACK = [None]


def ack(text='⏳ Making your post…'):
    """Instant 'working' message; removed again as soon as the post arrives so the chat stays clean."""
    try:
        r = requests.post(f'https://api.telegram.org/bot{TOKEN}/sendMessage', data={'chat_id': CHAT, 'text': text}, timeout=8)
        _ACK[0] = r.json()['result']['message_id']
    except Exception:
        _ACK[0] = None


def unack():
    if _ACK[0]:
        try:
            requests.post(f'https://api.telegram.org/bot{TOKEN}/deleteMessage', data={'chat_id': CHAT, 'message_id': _ACK[0]}, timeout=8)
        except Exception:
            pass
        _ACK[0] = None


def make_post(item):
    coin = coin_by_id(item['coin']) if item.get('coin') else None
    body = article_text(item.get('urls') or ([item['url']] if 't.me/' not in item.get('url', '') else [])) if item.get('url') else ''
    facts = (f'Headline: {item["title"]}\nSources: {", ".join(item.get("srcs") or [item.get("src", "")])}\n'
             + (f'Coin in this story: {coin["name"]} ({coin["sym"]}) {fmt_p(coin["price"])}, {coin["h24"]:+.1f}% in 24h\n' if coin else '')
             + (item.get('facts', '') + '\n') + (f'Telegram news posts about it:\n{item["tgtext"]}\n' if item.get('tgtext') else '')
             + (f'Article text:\n{body}\n' if body else ''))
    extra = 'This is a true crypto story: tell the post as a story with a twist.\n' if item.get('story') else ''
    if coin:                                                   # fetch the candles while the AI writes
        import threading
        threading.Thread(target=lambda: candles(coin, item.get('span') or '1d', None if item.get('focus') else item.get('t0')), daemon=True).start()
    p = parse_out(gemini(STYLE + FORMAT + extra + '\nFACTS:\n' + facts))
    if not p['title']:
        p = {'title': item['title'][:90], 'keyfact': '', 'reply': '', 'thread': '', 'tag': item.get('tag', 'BREAKING'), 'visual': '',
             'symbol': '', 'stat': '', 'timeline': '', 'versus': '', 'quote': '',
             'post': f'⚡ {item["title"]}' + (f'\n\n{coin["sym"]}: {fmt_p(coin["price"])} ({coin["h24"]:+.1f}% 24h)' if coin else '')}
        p['note'] = '⚠️ AI writer busy — simple version. Tap Make post again in a minute for the full one.'
    if not coin and p.get('symbol') not in ('', 'NONE') and re.search(r'\b' + re.escape(p['symbol']) + r'\b', facts, re.I):
        h = cg_search(p['symbol']); coin = coin_by_id(h['id']) if h else None
    chart_it = item.get('chart') or re.search(r'\b(pumps|dumps) \d', item['title']) or p.get('visual') == 'CHART'
    img = build_image(p, item, facts, coin if chart_it else None)
    k = hashlib.md5((item['title'] + str(NOW)).encode()).hexdigest()[:10]
    TGS.setdefault('designs', {})[k] = {'t': time.time(), 'p': p, 'item': {x: item.get(x) for x in ('title', 'src', 'tag', 'hack', 'url', 't0', 'focus', 'span', 'chart', 'story')},
                                         'facts': facts[:4000], 'coin': coin['id'] if coin else ''}
    TGS['designs'] = dict(sorted(TGS['designs'].items(), key=lambda kv: -kv[1]['t'])[:25])
    tg(caption(p, item.get('url', ''), item.get('src', ''), p.get('note', '')), img, post_buttons(k, p, item, coin))
    unack()


def switch_design(k, vis, msg_id=None):
    d = TGS.get('designs', {}).get(k)
    if not d:
        tg('That post is too old to redesign. Make it again from /top.'); return
    coin = coin_by_id(d['coin']) if d.get('coin') and vis == 'CHART' else None
    chat_action()
    img = build_image(d['p'], d['item'], d['facts'], coin, vis)
    cap = caption(d['p'], d['item'].get('url') or '', d['item'].get('src') or '')
    btn = post_buttons(k, d['p'], d['item'], coin or d.get('coin'))
    if not (msg_id and edit_photo(msg_id, img, cap, btn)):
        tg(cap, img, btn)


# ---------------- replies: X post link -> 3 ready replies ----------------
XLINK = re.compile(r'https?://(?:www\.|mobile\.)?(?:x|twitter|fxtwitter|vxtwitter|fixupx)\.com/([A-Za-z0-9_]+)/status(?:es)?/(\d+)', re.I)

VOICE = ('Voice: a calm, sharp crypto news account written by a real person. Plain clean English, short sentences, contractions are fine. '
         'Never use slang like bro, bruh, fam, ser, fren, gm, wagmi, ngmi, lfg, degen, ape, rekt, lol, lmao, "no cap", "fr", "ngl". '
         'Never use em dashes, hashtags, links, "Let that sink in", "This is huge", "game changer", "Translation:", or financial advice. '
         'Max one emoji, usually none.')
SLANG = re.compile(r'\b(bro|bros|bruh|fam|ser|fren|frens|gm|wagmi|ngmi|lfg|degen|degens|ape|aped|rekt|lol|lmao|ngl|fr|no cap)\b', re.I)
def gemini_voice(prompt):
    """Gemini, but if it slips into slang or em dashes, ask once for a clean rewrite."""
    out = gemini(prompt)
    if out and (SLANG.search(out) or '—' in out):
        bad = ', '.join(sorted({m.group(0).lower() for m in SLANG.finditer(out)})) or 'em dashes'
        again = gemini(prompt + f'\n\nYour last answer used {bad}. Rewrite it in clean, natural English without that. Same format.')
        out = again or out
    return out


def clean_voice(t):
    t = SLANG.sub('', t or '').replace(' — ', ', ').replace('—', ', ')
    return re.sub(r'\s{2,}', ' ', re.sub(r'\s+([,.!?])', r'\1', t)).strip(' ,')


REPLY_STYLES = [
    ('context', 'Add one piece of real context the post is missing (what happened before, who is involved, why it matters). Calm and informative.'),
    ('observation', 'Make one sharp, dry observation about what this really means. Understated, no exaggeration.'),
    ('history', 'Connect it to a well-known moment in crypto history that rhymes with this, only if you are sure of it. Short.'),
    ('numbers', 'Put the key number from the post in perspective (compare it to something people understand). Use only numbers from the post.'),
    ('calm_take', 'Give a level-headed take that cuts through the hype or panic in one or two sentences.'),
    ('light_humor', 'A light, clever line with a point behind it. Witty, not silly, no slang.'),
    ('question', 'Ask one genuine, smart question that experts would want answered about this (not engagement bait).'),
]
REPLY_EXAMPLES = ('Examples of the tone (do not copy them):\n'
                  '- "Third exchange this year to pause withdrawals after a hot wallet issue. Cold storage really isn\'t optional anymore."\n'
                  '- "The interesting part is the timing. This landed an hour before the ETF flow data."\n'
                  '- "$80M sounds big until you remember Ronin lost $600M the same way."\n'
                  '- "Quiet chart all week, then this. Someone knew before the headline did."\n')


OWNER_VIEW = ('The account owner is a long-term Bitcoin bull. Never mock Bitcoin, BTC holders or buying BTC; when news is good for '
              'Bitcoin, lean positive. ')
STANCE = {'agree': 'The owner AGREES with this post. Support it: back it up, add a fact that strengthens it, or build on it. Do not argue against it.',
          'disagree': 'The owner DISAGREES with this post. Push back politely with a clear reason or a fact. Respectful, no insults.',
          'neutral': 'The owner is NEUTRAL on this post. Add useful context or a sharp observation without taking a side.'}


def reply_rules(style, stance='neutral'):
    name, how = style
    return (VOICE + '\n' + OWNER_VIEW + STANCE.get(stance, STANCE['neutral']) + '\nYou are replying under an X post as the account "Chain Secrets". Write ONE reply that reads like a smart human wrote it '
            'in ten seconds: 8 to 25 words, max 180 characters, about what THIS post actually says. Never invent facts or numbers; if unsure, '
            'leave it out.\nStyle for this reply: ' + how + '\n' + REPLY_EXAMPLES +
            'Reply in exactly this format and nothing else:\n'
            'REPLY: <the reply>\n'
            'SYMBOL: <ticker of the crypto coin the post is mainly about, or NONE (stocks/companies are NONE)>\n'
            'CHART: <YES only if the post is about that coin\'s price moving and a 24h price chart would back up the reply, else NO>\n')



def read_x(user, sid):
    """Read a public X post for free: fxtwitter JSON first, X's own oEmbed as fallback."""
    r = get(f'https://api.fxtwitter.com/{user}/status/{sid}', timeout=8)
    try:
        t = r.json()['tweet']
        quote = (t.get('quote') or {}).get('text') or ''
        return {'text': t.get('text') or '', 'author': t['author'].get('screen_name') or user, 'name': t['author'].get('name') or user,
                'likes': t.get('likes') or 0, 'views': t.get('views') or 0, 'ts': t.get('created_timestamp') or time.time(),
                'quote': quote}
    except Exception:
        pass
    r = get('https://publish.twitter.com/oembed', params={'url': f'https://twitter.com/{user}/status/{sid}', 'omit_script': 'true'}, timeout=8)
    try:
        j = r.json(); m = re.search(r'(?is)<p[^>]*>(.*?)</p>', j['html'])
        txt = html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1))).strip() if m else ''
        return {'text': re.sub(r'\s+', ' ', txt), 'author': j.get('author_url', '').rsplit('/', 1)[-1] or user,
                'name': j.get('author_name') or user, 'likes': 0, 'views': 0, 'ts': time.time(), 'quote': ''}
    except Exception:
        return None


def coin_from_text(text, symbol=''):
    """Main coin of a post: cashtags first, then the AI's pick — only if the coin really appears in the text."""
    cand = ([symbol] if symbol and symbol != 'NONE' else []) + [x.upper() for x in re.findall(r'\$([A-Za-z]{2,8})\b', text)]
    for sym in dict.fromkeys(cand):
        h = cg_search(sym)
        c = coin_by_id(h['id']) if h else None
        if c and re.search(r'\b(' + re.escape(c['sym']) + '|' + re.escape(c['name']) + r')\b', text, re.I):
            return c
    return coin_in(' ' + text + ' ', collect_market())


def move_card(coin, tag='CHART'):
    """24h candle chart whose headline is computed from the same candles it shows."""
    rows, src, lab = candles(coin, '1d')
    if not rows:
        return None, ''
    mv = recent_move(rows, 86400)[0]
    title = f'{coin["name"]} {"up" if mv >= 0 else "down"} {abs(mv) * 100:.1f}% in 24 hours'
    try:
        return card.chart_card(title, coin, rows, lab, tag, src, focus=86400)[0], title
    except Exception as e:
        print('move card fail', repr(e)); return None, ''


def parse_replies(out):
    g = lambda k: (re.search(r'(?m)^' + k + r':\s*(.+)', out or '') or [None, ''])[1].strip().strip('"')
    rep = g('REPLY').replace(' — ', ', ').replace('—', ', ')
    return {'reply': rep, 'symbol': g('SYMBOL').upper().strip('$ '), 'chart': g('CHART').upper().startswith('Y')}


def reply_msg(rp, head, with_chart):
    return (head + f'\n\n<code>{E(rp["reply"])}</code>\n\n'
            + ('<i>📈 Attach this chart to the reply · tap the text to copy</i>' if with_chart else '<i>Tap to copy</i>'))


def cmd_reply(url, tgs, fresh=False):
    m = XLINK.search(url)
    if not m:
        tg('Send me an X post link, like <code>https://x.com/WatcherGuru/status/123…</code>'); return
    user, sid = m.group(1), m.group(2)
    if not fresh:
        ack('⏳ Reading the post…')
    post = read_x(user, sid)
    if not post or not post['text']:
        unack(); tg('Couldn\'t read that post (deleted, private or X blocked it). Paste its text here instead and I\'ll write replies.'); return
    if post['author'].lower() == 'thechainsecrets' or user.lower() == 'thechainsecrets':     # your own post: track it
        unack(); track_mine(user, sid, post); return
    save_xpost(post)
    ask_stance(post['text'] + (f'\n\n(Quoted post: {post["quote"]})' if post['quote'] else ''), post['author'], post, tgs, sid)


def ask_stance(text, author, post, tgs, key):
    """Show the post and ask the owner's side before writing the reply."""
    tgs.setdefault('replies', {})[key] = {**(tgs.get('replies', {}).get(key) or {}), 't': time.time(), 'text': text[:2000], 'author': author,
                                          'post': {x: (post or {}).get(x) for x in ('likes', 'ts')}}
    tgs['replies'] = dict(sorted(tgs['replies'].items(), key=lambda kv: -kv[1]['t'])[:30])
    stats = f' · ❤️ {post["likes"]:,}' if post and post.get('likes') else ''
    unack()
    tg(f'💬 <b>@{E(author)}</b>{stats}\n<i>{E(text[:300])}{"…" if len(text) > 300 else ""}</i>\n\n<b>Do you agree with this post?</b>', None,
       [('👍 Agree', f'ra:{key}:agree'), ('👎 Disagree', f'ra:{key}:disagree'), ('🤷 Neutral', f'ra:{key}:neutral')])


def on_stance(key, stance, tgs, mid):
    r = tgs.get('replies', {}).get(key)
    if not r:
        tg('That one is too old. Send the link again.'); return
    r['stance'] = stance
    try:                                                              # replace the question with the reply (clean chat)
        requests.post(f'https://api.telegram.org/bot{TOKEN}/deleteMessage', data={'chat_id': CHAT, 'message_id': mid}, timeout=8)
    except Exception:
        pass
    ack('⏳ Writing your reply…')
    reply_from_text(r['text'], r['author'], r.get('post'), tgs, key, stance)


def live_data(text):
    """Verified numbers for the coin the post is about (CoinGecko, now). Returns (line, coin) or ('', None)."""
    try:
        coin = coin_from_text(text, '')
    except Exception as e:
        print('live data fail', repr(e)[:100]); coin = None
    if not coin:
        return '', None
    return (f'{coin["name"]} ({coin["sym"]}) price {fmt_p(coin["price"])}, {coin["h24"]:+.1f}% in 24h, {coin["h1"]:+.1f}% in 1h (CoinGecko, now)'), coin


def best_reply(text, author, post, stance, used=()):
    """3 candidates -> numbers/shape checks -> AI fact-check + judge -> the single best one.
    Returns {'reply','style','symbol','chart','coin','live','level'} or None."""
    live, coin = live_data(text)
    styles = replies.pick_styles(brain.reply_stats(), used)
    note = ''
    for attempt in range(2):
        j = gemini_json(replies.candidate_prompt(VOICE + '\n' + OWNER_VIEW, text, author, STANCE.get(stance, STANCE['neutral']), styles, live, note))
        cands = []
        for c in (j or {}).get('replies') or []:
            r = clean_voice(str(c.get('reply', '')))
            if not r:
                continue
            n_ok, miss = replies.numbers_ok(r, text, live)
            s_ok, why = replies.shape_ok(r)
            cands.append({'style': str(c.get('style') or '?'), 'reply': r, 'nums_ok': n_ok, 'shape_ok': s_ok, 'why': why, 'miss': miss})
        if not cands:
            continue
        ok = [c for c in cands if c['nums_ok'] and c['shape_ok']]
        verdict = gemini_json(replies.judge_prompt(text, live, ok, STANCE.get(stance, STANCE['neutral']))) if ok else None
        best, level = replies.choose(ok, verdict)
        if best:
            sym = str((j or {}).get('symbol') or 'NONE').upper().strip('$ ')
            return {**best, 'symbol': sym, 'chart': bool((j or {}).get('chart')), 'coin': coin, 'live': live, 'level': level}
        bad = '; '.join(f'"{c["reply"][:60]}": ' + (f'numbers not in the post {c["miss"]}' if not c['nums_ok'] else c['why']) for c in cands if not (c['nums_ok'] and c['shape_ok']))
        note = ('Your last attempt was rejected (' + bad + '). Only use numbers that appear in the POST or LIVE DATA, and keep to the rules.') if bad else \
               'Your last attempt contained claims the post does not support. Stay strictly within what the post says.'
    return None


def reply_from_text(text, author, post, tgs, key, stance=None):
    stance = stance or (tgs.get('replies', {}).get(key) or {}).get('stance') or 'neutral'
    used = (tgs.get('replies', {}).get(key) or {}).get('styles', [])
    rp = None
    try:
        rp = best_reply(text, author, post, stance, used)
    except Exception as e:
        print('best_reply fail', repr(e)[:200])
    if not rp:
        unack(); tg('⚠️ I could not write a reply I trust for this post (the AI was busy or every draft failed my checks). Tap again in a minute.',
                    None, [('🔄 Try again', f'rr:{key}')]); return
    coin = rp['coin'] if rp['chart'] and rp['coin'] else None
    img = move_card(coin)[0] if coin else None
    stats = f' · ❤️ {post["likes"]:,}' if post and post.get('likes') else ''
    stats += f' · {ago(post["ts"])}' if post and post.get('ts') else ''
    face = {'agree': '👍 agreeing', 'disagree': '👎 pushing back', 'neutral': '🤷 neutral'}[stance]
    note = replies.age_note(post)
    head = (f'💬 <b>Reply for @{E(author)}</b> · {face}{stats}\n<i>{E(text[:160])}{"…" if len(text) > 160 else ""}</i>'
            + (f'\n{note}' if note else ''))
    rid = hashlib.md5(f'{key}{time.time()}'.encode()).hexdigest()[:8]
    tgs.setdefault('replies', {})[key] = {**(tgs.get('replies', {}).get(key) or {}), 't': time.time(), 'text': text[:2000], 'author': author,
                                          'styles': used + [rp['style']], 'stance': stance, 'post': {x: (post or {}).get(x) for x in ('likes', 'ts')}}
    tgs['replies'] = dict(sorted(tgs['replies'].items(), key=lambda kv: -kv[1]['t'])[:30])
    brain.reply_add({'rid': rid, 't': time.time(), 'key': key, 'author': author, 'style': rp['style'], 'stance': stance, 'reply': rp['reply'],
                     'coin': coin['sym'] if coin else None, 'chart': bool(img), 'check': rp['level'],
                     'age_min': round((time.time() - post['ts']) / 60) if post and post.get('ts') else None})
    brain.save()
    unack()
    body = (head + f'\n\n<code>{E(rp["reply"])}</code>\n\n' + (f'📊 <i>Live: {E(rp["live"])}</i>\n' if rp['live'] else '')
            + replies.check_line(rp['level'], rp['live']) + '\n'
            + ('<i>📈 Attach this chart to the reply · tap the text to copy</i>' if img else '<i>Tap to copy</i>'))
    other = [x for x in ('agree', 'disagree', 'neutral') if x != stance]
    tg(body, img, [('🔄 Another one', f'rr:{key}')]
       + [({'agree': '👍 Agree instead', 'disagree': '👎 Disagree instead', 'neutral': '🤷 Neutral instead'}[x], f'ra:{key}:{x}:k') for x in other]
       + [('✅ I posted it', f'rf:{rid}:p'), ('👍 It worked', f'rf:{rid}:w'), ('👎 Didn\'t work', f'rf:{rid}:n')])


def on_reply_feedback(data):
    rid, what = data.split(':')[1:3]
    if what == 'p':
        r = brain.reply_mark(rid, 'posted', True); msg = '✅ Logged. Paste the link of your reply here later and I will read its likes and views.'
    else:
        r = brain.reply_mark(rid, 'outcome', 1 if what == 'w' else -1)
        msg = '👍 Noted. I will write more like this one.' if what == 'w' else '👎 Noted. I will use that style less.'
    brain.save()
    tg(msg if r else 'That reply is too old to log.')


def more_replies(key, tgs):
    r = tgs.get('replies', {}).get(key)
    if not r:
        tg('That one is too old. Send the link again.'); return
    chat_action('typing')
    reply_from_text(r['text'], r['author'], r.get('post'), tgs, key)


# ---------------- reply window: viral story -> who will post + ready replies ----------------
VIRAL = 85
WHO = [  # (story keywords, accounts most likely to post it within minutes)
    (r'hack|exploit|drain|stole|attack|breach|phish', ['zachxbt', 'PeckShieldAlert', 'lookonchain', 'WuBlockchain', 'Cointelegraph']),
    (r'\betf|blackrock|fidelity|grayscale|inflow|outflow', ['EricBalchunas', 'JSeyff', 'WatcherGuru', 'BitcoinMagazine', 'CoinDesk']),
    (r'\bsec\b|cftc|regulat|congress|senate|bill|law|trump|white house|fed\b|rate', ['WatcherGuru', 'CoinDesk', 'Cointelegraph', 'BitcoinMagazine']),
    (r'arrest|charged|sentenc|court|lawsuit|sued|guilty|fraud|scam', ['zachxbt', 'WatcherGuru', 'Cointelegraph', 'CoinDesk']),
    (r'whale|transfer|moved|dormant|wallet|sold|buys?\b|purchase|treasury|strategy|microstrategy',
     ['whale_alert', 'lookonchain', 'saylor', 'WatcherGuru', 'BitcoinMagazine']),
    (r'binance|\bcz\b', ['cz_binance', 'WuBlockchain', 'WatcherGuru']),
    (r'ethereum|\beth\b|vitalik', ['VitalikButerin', 'lookonchain', 'WatcherGuru']),
    (r'crash|plung|liquidat|dump|surge|soar|record|all-time high|rally|bitcoin|btc', ['WatcherGuru', 'BitcoinMagazine', 'whale_alert', 'lookonchain']),
]


def who_posts(title):
    acc = []
    for rx, names in WHO:
        if re.search(rx, title.lower()):
            acc += [n for n in names if n not in acc]
    for n in ['WatcherGuru', 'Cointelegraph']:
        if n not in acc:
            acc.append(n)
    return acc[:5]


def viral_alert(st, sc, lead, coin, srcs, g, age, pr=None):
    mk = remember(st, g, lead, coin, srcs)
    import random
    post_txt = f'{lead["title"]} (sources: {", ".join(sorted(srcs))})' + (f'. {coin["name"]} ({coin["sym"]}) is {fmt_p(coin["price"])}, {coin["h24"]:+.1f}% in 24h' if coin else '')
    rp = None
    try:
        rp = best_reply(post_txt, 'a big news account', None, 'neutral')
    except Exception as e:
        print('viral best_reply fail', repr(e)[:150])
    if rp:
        rp['reply'] = clean_voice(rp['reply'])
    else:                                                              # fallback: the old single-shot writer
        rp = parse_replies(gemini_voice(reply_rules(random.choice(REPLY_STYLES), 'neutral') + '\nThe post you reply to is a big account breaking this news:\n'
                                  f'Headline: {lead["title"]}\nSources: {", ".join(sorted(srcs))}'
                                  + (f'\nCoin: {coin["name"]} ({coin["sym"]}) {fmt_p(coin["price"])}, {coin["h24"]:+.1f}% 24h' if coin else '')))
        rp['reply'] = clean_voice(rp['reply']); rp['level'] = None; rp['live'] = ''
    acc = who_posts(lead['title'])
    head = (f'🔥 <b>GOING VIRAL · REPLY WINDOW OPEN</b>\n<b>{E(lead["title"])}</b>\n{confirmed(srcs)} · {chance_txt(pr, sc)} · {age*60:.0f} min ago\n\n'
            f'👀 Watch for posts from: ' + ' · '.join(f'<a href="https://x.com/{a}">@{a}</a>' for a in acc)
            + '\nReply in the first 15 minutes with 👇')
    img = move_card(coin)[0] if coin and rp.get('chart') else None
    if rp['reply']:
        chk = ('\n' + replies.check_line(rp['level'], rp['live'])) if rp.get('level') else ''
        tg(reply_msg(rp, head, bool(img)) + chk, img, fb_buttons(mk))
    else:
        tg(head, img, fb_buttons(mk))


# ---------------- easy daily use: menu, briefings, feedback, tracking, weekly report ----------------
MENU = [['📋 Today\'s kit', '📰 Top stories'], ['📊 Movers', '💬 Reply to a post'], ['🎬 Studio', '📖 Story']]
MENU_V = 5


def send_menu(text='👇 Your menu is ready at the bottom of the chat.', job=None):
    def btn(b):
        if b == '🎬 Studio':                                             # opens the Studio Mini App (sendData works from keyboard buttons)
            return {'text': b, 'web_app': {'url': STUDIO_URL + (f'?job={job}' if job else '')}}
        return {'text': b}
    kb = {'keyboard': [[btn(b) for b in row] for row in MENU], 'resize_keyboard': True, 'is_persistent': True}
    try:
        requests.post(f'https://api.telegram.org/bot{TOKEN}/sendMessage', timeout=10,
                      data={'chat_id': CHAT, 'text': text, 'reply_markup': json.dumps(kb)})
    except Exception:
        pass


def brief(tgs, label):
    """3 best stories right now, ranked by the brain (or the score while it learns). Never repeats a story within 2 days."""
    git_sync()
    st = load_state(); b = brain.load(); pr = st.get('probs', {})
    rows = []
    for k, sc, age, ns in st.get('top') or []:
        it = st.get('menu', {}).get(k)
        if not it or k in b['briefed']:
            continue
        if (k in pr and pr[k] < 0.35 and sc < 60) or (k not in pr and sc < 45):  # only stories worth posting
            continue
        if junk_story(it['title'], [{'title': it['title'], 'src': it.get('src', '')}], it.get('coin')):
            continue
        rows.append((pr.get(k, sc / 100 * 0.9), k, sc, ns, it))
    rows.sort(key=lambda r: -r[0])
    rows = rows[:3]
    if not rows:
        return
    msg = f'{label}\n<b>Your {"3 best stories" if len(rows) == 3 else "best stories" if len(rows) > 1 else "best story"} now</b> · tap a number → image + post\n'
    for n, (p, k, sc, ns, it) in enumerate(rows, 1):
        b['briefed'][k] = time.time()
        chance = f'🔥 {pr[k] * 100:.0f}%' if k in pr else f'score {sc}'
        msg += f'\n<b>{n}.</b> {E(it["title"])}\n    <i>{chance} · {"✅ confirmed" if ns >= 2 else "⚠️ unconfirmed"} · {ns} src</i>'
    brain.save()
    tg(msg, None, [(f'📝 {n}', 'p:' + r[1]) for n, r in enumerate(rows, 1)])


def daily_kit(tgs):
    """15:00 Beirut: your posting plan for the day, everything one tap away.
    1 news post · 1 chart post · 1 opinion post · who to reply to tonight."""
    git_sync()
    st = load_state(); b = brain.load(); pr = st.get('probs', {})
    rows = []
    for k, sc, age, ns in st.get('top') or []:
        it = st.get('menu', {}).get(k)
        if it and not junk_story(it['title'], [{'title': it['title'], 'src': it.get('src', '')}], it.get('coin')):
            rows.append((pr.get(k, sc / 100), k, sc, ns, it))
    rows.sort(key=lambda r: -r[0])
    news = rows[0] if rows else None
    r = get('https://api.coingecko.com/api/v3/coins/markets', params={'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 100,
                                                                       'page': 1, 'price_change_percentage': '24h'})
    try:
        mv = max([c for c in r.json() if not NOT_CRYPTO.search(c['name']) and not re.search(r'usd|eur|dai|gold|wrapped|staked|bridged', c['name'], re.I)],
                 key=lambda c: abs(c.get('price_change_percentage_24h_in_currency') or 0))
    except Exception:
        mv = None
    theme = news[4]['title'] if news else 'the crypto market today'
    q = clean_voice(gemini_voice(VOICE + '\n' + OWNER_VIEW + '\nWrite ONE short X post (max 200 characters) that shares a clear opinion about '
                                 'this topic and invites people to reply with theirs. A real take, not engagement bait. Post text only.\n\nTopic: ' + theme) or '')
    m = '📋 <b>Your posting kit for today</b>\n'
    btn = []
    if news:
        m += f'\n<b>1. 📰 News post</b>\n{E(news[4]["title"])}\n<i>{"✅ confirmed" if news[3] >= 2 else "⚠️ unconfirmed"} · {news[3]} sources</i>\n'
        btn.append(('📰 Make news post', 'p:' + news[1])); b['briefed'][news[1]] = time.time()
    if mv:
        ch = mv.get('price_change_percentage_24h_in_currency') or 0
        m += f'\n<b>2. 📊 Chart post</b>\n{E(mv["name"])} ({mv["symbol"].upper()}) {ch:+.1f}% in 24h, biggest move in the top 100\n'
        btn.append((f'📊 {mv["symbol"].upper()} chart', 'm:' + mv['id']))
    if q:
        tgs['kit_q'] = theme
        m += f'\n<b>3. 💬 Your take</b> (tap to copy, edit it to your words)\n<code>{E(q)}</code>\n'
        btn.append(('🔄 Another take', 'kq:'))
    if news:
        m += '\n<b>🎯 Reply tonight under:</b> ' + ' · '.join(f'@{a}' for a in who_posts(news[4]['title'])[:4]) + '\n'
    m += '\n<i>Then 10–15 replies between 20:00 and 23:00. That\'s the whole day.</i>'
    brain.save()
    tg(m, None, btn)


def kit_take(tgs):
    theme = tgs.get('kit_q') or 'the crypto market today'
    chat_action('typing')
    q = clean_voice(gemini_voice(VOICE + '\n' + OWNER_VIEW + '\nWrite ONE short X post (max 200 characters) with a different, clear opinion '
                                 'about this topic that invites replies. Post text only.\n\nTopic: ' + theme) or '')
    tg(f'💬 <b>Your take</b>\n<code>{E(q)}</code>' if q else '⚠️ The AI writer is busy, tap again in a minute.')


def on_feedback(k, val, tgs):
    it = menu_item(k, tgs)
    if not it:
        return 'Too old'
    sk = brain.mark(it['title'], 'fb', 1 if val == '1' else -1, time.time())
    brain.save()
    return 'Saved 👍 — more like this' if val == '1' else 'Saved 👎 — fewer like this'


def on_posted(k):
    d = TGS.get('designs', {}).get(k)
    if not d:
        return 'Too old'
    t = d['item'].get('title') or d['p'].get('title', '')
    brain.mark(t, 'posted', True, time.time())
    with brain.LOCK:
        brain.load()['posted'].append({'t': time.time(), 'title': t[:160], 'tp': brain.topics(t + ' ' + d['p'].get('title', ''))})
    brain.save()
    tg('✅ Logged. Send me the link of your X post and I\'ll track how it does.')
    return 'Logged ✅'


def track_mine(user, sid, post):
    linked = brain.reply_link(post['text'], f'https://x.com/{user}/status/{sid}')
    if linked:
        brain.save(); tg(f'✅ Matched to the {linked["style"]} reply I wrote. I will read its likes and views tomorrow and learn which style works for you.')
    with brain.LOCK:
        brain.load()['mine'][sid] = {'t': time.time(), 'url': f'https://x.com/{user}/status/{sid}', 'text': post['text'][:280],
                                     'tp': brain.topics(post['text']), 'likes': post.get('likes', 0), 'views': post.get('views', 0), 'checked': 0}
    brain.save()
    tg('📈 Tracking your post. I\'ll check its likes and views tomorrow and learn from it.')


def check_mine():
    """24h after you post: read your post's real likes/views (free) so the brain learns what works on YOUR account."""
    for sid, m in list(brain.load()['mine'].items()):
        if m.get('checked') or time.time() - m['t'] < 24 * 3600:
            continue
        u = XLINK.search(m['url'])
        p = read_x(u.group(1), sid) if u else None
        with brain.LOCK:
            if p:
                m.update({'likes': p.get('likes', 0), 'views': p.get('views', 0)})
                for r in brain.load()['replies']:                      # a reply draft linked to this post: store its real result
                    if r.get('url') == m['url']:
                        r.update({'likes': p.get('likes', 0), 'views': p.get('views', 0)})
            m['checked'] = time.time()
    brain.save()


def save_xpost(post):
    if post and post.get('likes'):
        with brain.LOCK:
            brain.load()['xposts'].append({'a': post['author'], 'text': post['text'][:500], 'likes': post['likes'],
                                           'views': post.get('views', 0), 't': time.time()})


def weekly_report():
    b = brain.load(); now = time.time(); wk = 7 * 86400
    posted = [p for p in b['posted'] if now - p['t'] < wk]
    tops = {}
    for p in posted:
        for t in p.get('tp') or ['other']:
            tops[t] = tops.get(t, 0) + 1
    mine = [m for m in b['mine'].values() if now - m['t'] < wk + 86400 and m.get('checked')]
    best = max(mine, key=lambda m: m.get('likes', 0), default=None)
    missed = sorted([s for s in b['stories'].values() if now - s['t0'] < wk and s['lab'] == 1 and not s.get('posted')],
                    key=lambda s: -(s.get('vmax', 0) + s.get('smax', 0) / 3))[:3]
    stt = brain.status()
    m = '📅 <b>Your week on Chain Secrets</b>\n\n'
    m += f'✍️ Posts made: <b>{len(posted)}</b>' + (f' · most: {", ".join(f"{k} ({v})" for k, v in sorted(tops.items(), key=lambda x: -x[1])[:3])}' if tops else '') + '\n'
    if mine:
        m += f'📈 Tracked X posts: {len(mine)} · avg ❤️ {sum(x.get("likes", 0) for x in mine) / len(mine):.0f} · avg 👁 {sum(x.get("views", 0) for x in mine) / len(mine):,.0f}\n'
        m += f'🏆 Best: <i>{E(best["text"][:100])}</i> ({best.get("likes", 0)} ❤️)\n'
    else:
        m += '📈 No tracked X posts yet — send me your post links after posting.\n'
    if missed:
        m += '\n🙈 <b>Big stories you missed</b>\n' + '\n'.join(f'• {E(s["title"][:110])}' for s in missed) + '\n'
    m += (f'\n🧠 Brain: {stt["labeled"]} stories learned ({stt["viral"]} viral)'
          + (f' · accuracy score {stt["auc"]:.2f}' if stt.get('auc') else '') + (' · ✅ predicting' if stt['ready'] else ' · still learning'))
    tg(m)


def brain_status():
    s = brain.status()
    m = '🧠 <b>Chain Radar brain</b>\n\n'
    m += f'Stories logged: <b>{s["stories"]}</b> ({s["days"]:.1f} days of data)\nLearned (6h+ old): <b>{s["labeled"]}</b> · went viral: <b>{s["viral"]}</b>\n'
    m += f'Your taps: {s["fb"]} 👍/👎 · tracked X posts: {s["mine"]} · big-account posts seen: {s["xposts"]}\n'
    m += f'Telegram channels live: {len(s["chan"])}\n\n'
    if s['ready']:
        m += f'✅ <b>Predicting.</b> Accuracy score {s["auc"]:.2f} (0.5 = guessing, 1.0 = perfect). Alerts now show viral chance %.'
    else:
        need = max(0, 150 - s['labeled'])
        m += (f'⏳ <b>Still learning.</b> ~{need} more stories needed before it predicts (about {max(1, need // 40 + 1)} days). '
              'Until then alerts use the score. Tap 👍/👎 to teach it your taste faster.')
    sh = shorts.status()
    m += f'\n\n🎬 <b>Shorts brain</b>: {sh["shorts"]:,} Shorts studied · {sh["analyzed"]} watched by AI · {sh["winners"]} big winners'
    tg(m)


_SCHED = {}


def scheduler(tgs):
    """Runs inside the always-on listener, on Beirut time: on-this-day 12:00, kit 15:00, briefing 20:00, training 03:30,
    Shorts data 05:00 + analysis 06:00, own-post check 12:00, Sunday reports 18:00."""
    import threading
    now = datetime.now(BEIRUT); day = now.strftime('%Y-%m-%d')
    jobs = []

    def due(key, hour, minute=0, window=40, weekday=None):
        if weekday is not None and now.weekday() != weekday:
            return False
        if now.hour == hour and minute <= now.minute < minute + window and tgs.get(key) != day:
            tgs[key] = day
            return True
        return False
    if due('otd_day', 12):
        jobs.append(lambda: on_this_day(tgs))
    if due('kit', 15):
        jobs.append(lambda: daily_kit(tgs))
    if due('brief17', 20):
        jobs.append(lambda: brief(tgs, '🌆 <b>Evening briefing</b>'))
    if due('trained', 3, 30):
        jobs.append(lambda: (brain.label_due(time.time()), brain.train(), brain.save()))
    if due('checked', 12, 40, 60):
        jobs.append(check_mine)
    if due('weekly', 18, weekday=6):
        jobs.append(weekly_report)
    if due('sh_collect', 5):
        jobs.append(lambda: shorts.collect())
    if due('sh_analyze', 6):
        jobs.append(lambda: shorts.analyze_batch(60, [m for m in gemini_models() if 'gemma' not in m][:3]))
    if due('sh_weekly', 18, 45, weekday=6):
        jobs.append(shorts_report)
    for j in jobs:
        def run(j=j):
            try:
                j()
            except Exception as e:
                print('job fail', repr(e))
        threading.Thread(target=run, daemon=True).start()


# ---------------- any coin: chart + a ready sentence ----------------
WIN = {'1h': (3600, '8h', '1 hour'), '24h': (86400, '1d', '24 hours'), '7d': (7 * 86400, '7d', '7 days')}


def resolve_coin(q):
    """Ticker or name -> coin. CoinGecko first (never stocks); Binance-only coins still work (price from Binance)."""
    q = q.strip().lstrip('$').upper()
    q = re.sub(r'(USDT|USDC|USD|PERP)$', '', q) or q
    h = cg_search(q, strict=False)
    if not h:
        r = get('https://api.coingecko.com/api/v3/search', params={'query': q})
        hits = [x for x in (r.json().get('coins', []) if r else []) if x['name'].upper() == q and not NOT_CRYPTO.search(x['name'])]
        h = hits[0] if hits else None
    c = coin_by_id(h['id']) if h else None
    if c:
        return c
    rows = binance(q, 3600, limit=2)
    if rows:
        return {'id': '', 'sym': q, 'name': q, 'price': rows[-1][4], 'h1': 0, 'h24': 0, 'rank': 999}
    return None


def coin_query(t):
    """Find a coin request in a sentence: '$PEPE', 'chart pepe', 'pepe chart', 'PEPEUSDT', or a lone ticker."""
    m = re.search(r'\$([A-Za-z0-9]{2,12})\b', t)
    if m:
        return m.group(1)
    m = re.search(r'(?i)\bchart\s+(?:of\s+|for\s+)?([A-Za-z0-9]{2,15})\b', t) or re.search(r'(?i)\b([A-Za-z0-9]{2,15})\s+chart\b', t)
    if m:
        return m.group(1)
    m = re.match(r'^([A-Z0-9]{2,12})(?:USDT|/USDT)?$', t.strip())          # lone ticker only in CAPS: PEPE, SOLUSDT
    return m.group(1) if m and not m.group(1).isdigit() else None


def coin_window(coin):
    """Pick the window that shows the real story: last hour if that's where the move is, else 24h."""
    r8, _, _ = candles(coin, '8h'); r24, _, _ = candles(coin, '1d')
    m1 = recent_move(r8, 3600)[0] if r8 else 0
    m24 = recent_move(r24, 86400)[0] if r24 else 0
    return '1h' if abs(m1) >= 0.04 and abs(m1) >= 0.5 * abs(m24) else '24h'


def coin_render(coin, win):
    secs, span, words_ = WIN[win]
    rows, src, lab = candles(coin, span)
    if not rows:
        return None, None, None
    mv, p0, p1 = recent_move(rows, secs)
    verb = ('surges' if mv >= 0.08 else 'climbs' if mv >= 0 else 'plunges' if mv <= -0.08 else 'slips')
    title = f'{coin["name"]} {verb} {abs(mv) * 100:.1f}% in {words_}'
    try:
        img = card.chart_card(title, coin, rows, lab, 'MOVER', src, focus=secs)[0]
    except Exception as e:
        print('coin card fail', repr(e)); return None, None, None
    return img, title, {'mv': mv, 'p0': p0, 'p1': p1, 'src': src, 'win': words_}


def coin_heads(coin):
    junk = (r'predict|could be worth|millionaire|should you buy|buy now|top \d|which is|best crypto|to buy|forecast|\?$|price today|'
            r'live price|to usd|market ?cap|price chart|price index|\bvs\b|\.lol|\.io\)|presale|airdrop guide')
    if coin['name'] == coin['sym']:
        q = f'{coin["sym"]} crypto'
    else:
        q = f'"{coin["name"]}" crypto'
    other = r'\b(doge|baby|shib|floki|mini|inu|2\.0|classic)\s+' + re.escape(coin['name'])     # 'Doge Pepe' is not Pepe
    return [h for h in gnews(q, 15) if re.search(r'\b(' + re.escape(coin['name']) + '|' + re.escape(coin['sym']) + r')\b', h['title'], re.I)
            and not re.search(junk, h['title'], re.I) and not re.search(other, h['title'], re.I) and time.time() - h['ts'] < 36 * 3600][:2]


def coin_sentence(coin, title, m, heads, other=False):
    facts = (f'Coin: {coin["name"]} ({coin["sym"]}). Move: {m["mv"] * 100:+.1f}% in {m["win"]} (from {fmt_p(m["p0"])} to {fmt_p(m["p1"])}, '
             f'real {m["src"]} candles).\n' + ('Recent headlines:\n' + '\n'.join(f'- {h["title"]} ({h["src"]}, {ago(h["ts"])})' for h in heads)
                                                  if heads else 'No coin-specific news found: do not invent a reason.'))
    out = gemini_voice(VOICE + '\nWrite ONE X post (max 230 characters) to go with a candle chart of this move. State the move with the real '
                 'number, and if a headline explains it, say why in plain words. If there is no news, you can note the move came '
                 'without a clear headline. ' + ('Take a different angle than usual. ' if other else '') + 'Reply with the post text only.\n\n' + facts)
    return clean_voice(out.strip().strip('"')) if out else f'{title}. {fmt_p(m["p0"])} → {fmt_p(m["p1"])}.'


def coin_buttons(k, win):
    b = [(('• ' if w == win else '') + w.upper(), f'cw:{k}:{w}') for w in ('1h', '24h', '7d')]
    return b + [('🔄 Another sentence', f'cs:{k}'), ('📝 Full post', f'cp:{k}')]


def coin_caption(d):
    c = f'<code>{E(d["sentence"])}</code>'
    if d.get('heads'):
        h = d['heads'][0]
        c += f'\n\n📰 <a href="{E(h["url"])}">{E(h["title"][:120])}</a> <i>({E(h["src"])}, {ago(h["ts"])})</i>'
    return c + f'\n<i>Tap to copy · {d["src"]} candles</i>'


def coin_view(q, tgs, msg_id=None):
    """'$PEPE' / 'chart sol' / a movers button -> real chart + a ready sentence to post."""
    coin = coin_by_id(q[3:]) if q.startswith('id:') else resolve_coin(q)
    if not coin:
        unack(); tg(f'Couldn\'t find a coin called <b>{E(q)}</b> on CoinGecko or Binance. Try its ticker, like <code>$PEPE</code>.'); return
    win = coin_window(coin)
    img, title, m = coin_render(coin, win)
    if not img:
        unack(); tg(f'No candle data for {E(coin["name"])} right now.'); return
    heads = coin_heads(coin) if coin.get('id') else []
    k = hashlib.md5((coin['sym'] + str(time.time())).encode()).hexdigest()[:10]
    d = {'t': time.time(), 'coin': coin, 'win': win, 'title': title, 'm': m, 'heads': heads, 'src': m['src']}
    d['sentence'] = coin_sentence(coin, title, m, heads)
    tgs.setdefault('coins', {})[k] = d
    tgs['coins'] = dict(sorted(tgs['coins'].items(), key=lambda kv: -kv[1]['t'])[:20])
    unack()
    tg(coin_caption(d), img, coin_buttons(k, win))


def coin_switch(k, win, tgs, msg_id):
    d = tgs.get('coins', {}).get(k)
    if not d:
        tg('That chart is too old. Ask again, e.g. <code>$PEPE</code>.'); return
    chat_action()
    img, title, m = coin_render(d['coin'], win)
    if not img:
        tg('No candle data for that window.'); return
    d.update({'win': win, 'title': title, 'm': m, 'src': m['src']})
    d['sentence'] = coin_sentence(d['coin'], title, m, d['heads'])
    if not (msg_id and edit_photo(msg_id, img, coin_caption(d), coin_buttons(k, win))):
        tg(coin_caption(d), img, coin_buttons(k, win))


def coin_resentence(k, tgs, msg_id):
    d = tgs.get('coins', {}).get(k)
    if not d:
        return
    chat_action('typing')
    d['sentence'] = coin_sentence(d['coin'], d['title'], d['m'], d['heads'], other=True)
    try:
        kb = {'inline_keyboard': [[{'text': a, 'callback_data': b} for a, b in row] for row in
                                  [coin_buttons(k, d['win'])[i:i + 3] for i in range(0, 6, 3)]]}
        requests.post(f'https://api.telegram.org/bot{TOKEN}/editMessageCaption', timeout=10,
                      data={'chat_id': CHAT, 'message_id': msg_id, 'caption': coin_caption(d), 'parse_mode': 'HTML', 'reply_markup': json.dumps(kb)})
    except Exception:
        tg(coin_caption(d))


def coin_fullpost(k, tgs):
    d = tgs.get('coins', {}).get(k)
    if not d:
        return
    c = d['coin']; h = d['heads'][0] if d['heads'] else None
    secs, span, _ = WIN[d['win']]
    make_post({'title': d['title'], 'url': h['url'] if h else '', 'src': h['src'] if h else d['src'], 'coin': c.get('id', ''), 'chart': True,
               'tag': 'MARKET', 'focus': secs, 'span': span,
               'facts': f'Real move: {d["m"]["mv"] * 100:+.1f}% in {d["m"]["win"]} ({fmt_p(d["m"]["p0"])} -> {fmt_p(d["m"]["p1"])}).\n'
                        + ('\n'.join(f'- {x["title"]} ({x["src"]})' for x in d['heads']) if d['heads'] else 'No coin-specific news found; do not invent a reason.')})


def movers_msg():
    r = get('https://api.coingecko.com/api/v3/coins/markets', params={'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 250,
                                                                       'page': 1, 'price_change_percentage': '1h,24h'})
    try:
        m = [{'id': c['id'], 'sym': c['symbol'].upper(), 'price': c['current_price'] or 0, 'h1': c.get('price_change_percentage_1h_in_currency') or 0,
              'h24': c.get('price_change_percentage_24h_in_currency') or 0} for c in r.json() if not NOT_CRYPTO.search(c['name'])
             and not re.search(r'usd|eur|dai|gold|wrapped|staked|bridged', c['name'], re.I)]
    except Exception:
        return None, None
    by = {c['sym']: c for c in m}
    upn = sum(1 for c in m if c['h24'] > 0)
    head = f'📊 <b>Market pulse</b> · top 250 · updated {datetime.now(timezone.utc):%H:%M} UTC\n'
    for sym in ('BTC', 'ETH', 'SOL'):
        if sym in by:
            c = by[sym]; head += f'{"🟢" if c["h24"] >= 0 else "🔴"} {sym} {fmt_p(c["price"])} ({c["h24"]:+.1f}%)   '
    head += f'\n{"🟢" if upn >= len(m) / 2 else "🔴"} {upn} up · {len(m) - upn} down\n'
    row = lambda c: f'{c["sym"][:6]:<6}{fmt_p(c["price"]):>11}{c["h24"]:>+8.1f}%{c["h1"]:>+7.1f}%'
    up = sorted(m, key=lambda c: -c['h24'])[:5]; dn = sorted(m, key=lambda c: c['h24'])[:5]
    fast = sorted(m, key=lambda c: -abs(c['h1']))[:4]
    msg = (head + '\n🚀 <b>Top gainers</b>\n<pre>' + f'{"COIN":<6}{"PRICE":>11}{"24H":>9}{"1H":>8}\n' + '\n'.join(map(row, up)) + '</pre>'
           + '\n🩸 <b>Top losers</b>\n<pre>' + '\n'.join(map(row, dn)) + '</pre>'
           + '\n⚡ <b>Moving right now (1h):</b> ' + ', '.join(f'{c["sym"]} {c["h1"]:+.1f}%' for c in fast)
           + '\n\n👇 Tap a coin → chart + sentence. Or type any coin, e.g. <code>$PEPE</code>')
    btn = [(f'{"🚀" if c["h24"] > 0 else "🩸"} {c["sym"]}', f'm:{c["id"]}') for c in up + dn]
    btn += [(f'⚡ {c["sym"]}', f'm:{c["id"]}') for c in fast if c not in up + dn][:2] + [('🔄 Refresh', 'mr:')]
    return msg, btn


def cmd_movers(tgs, msg_id=None):
    msg, btn = movers_msg()
    if not msg:
        tg('Market data unavailable, try again in a minute.'); return
    if msg_id:                                                       # refresh in place, no new message
        kb = {'inline_keyboard': [[{'text': a, 'callback_data': b} for a, b in btn[i:i + 3]] for i in range(0, len(btn), 3)]}
        r = requests.post(f'https://api.telegram.org/bot{TOKEN}/editMessageText', timeout=10,
                          data={'chat_id': CHAT, 'message_id': msg_id, 'text': msg, 'parse_mode': 'HTML', 'reply_markup': json.dumps(kb)})
        if r.ok or 'not modified' in r.text:
            return
    tg(msg, None, btn)


# ---------------- on this day: real stories from past years ----------------
FAMOUS = {  # well-documented dates only
    (10, 31): [(2008, 'Satoshi Nakamoto publishes the Bitcoin whitepaper')],
    (1, 3): [(2009, 'The Bitcoin genesis block is mined')],
    (1, 12): [(2009, 'First Bitcoin transaction: Satoshi sends 10 BTC to Hal Finney')],
    (5, 22): [(2010, 'Bitcoin Pizza Day: 10,000 BTC buys two pizzas')],
    (11, 28): [(2012, 'Bitcoin\'s first halving')], (7, 9): [(2016, 'Bitcoin\'s second halving')],
    (5, 11): [(2020, 'Bitcoin\'s third halving')], (4, 20): [(2024, 'Bitcoin\'s fourth halving')],
    (2, 24): [(2014, 'Mt. Gox halts all trading and goes offline')],
    (6, 17): [(2016, 'The DAO is hacked: about 3.6 million ETH drained')],
    (7, 30): [(2015, 'Ethereum mainnet launches')], (8, 1): [(2017, 'Bitcoin Cash splits from Bitcoin')],
    (12, 10): [(2017, 'Bitcoin futures start trading on CBOE')], (12, 17): [(2017, 'Bitcoin peaks near $20,000 for the first time')],
    (3, 12): [(2020, 'Black Thursday: Bitcoin crashes about 40% in a day')],
    (4, 14): [(2021, 'Coinbase goes public on Nasdaq')], (9, 7): [(2021, 'Bitcoin becomes legal tender in El Salvador')],
    (8, 10): [(2021, 'Poly Network hacked for $611 million')],
    (5, 9): [(2022, 'UST loses its dollar peg, starting the Terra/LUNA collapse')],
    (9, 15): [(2022, 'The Ethereum Merge: Ethereum switches to proof of stake')],
    (11, 8): [(2022, 'Binance announces a deal to rescue FTX')], (11, 11): [(2022, 'FTX files for bankruptcy')],
    (11, 21): [(2023, 'CZ pleads guilty and steps down as Binance CEO')],
    (1, 10): [(2024, 'The SEC approves the first spot Bitcoin ETFs')],
    (12, 5): [(2024, 'Bitcoin crosses $100,000 for the first time')], (2, 21): [(2025, 'Bybit hacked for about $1.5 billion')],
}
OTD_JUNK = re.compile(r'price (analysis|prediction|today|update)|technical analysis|\bTA\b|forecast|could reach|should you|how to|'
                      r'what is|explained|weekly|daily|newsletter|podcast|roundup|recap|markets? wrap|\?$', re.I)


def on_this_day(tgs):
    now = datetime.now(timezone.utc); md = (now.month, now.day)
    ack(f'⏳ Digging through crypto history for {now:%B %d}…')
    from concurrent.futures import ThreadPoolExecutor

    def year(y):
        try:
            d = now.replace(year=y)
        except ValueError:
            return []
        q = f'(bitcoin OR crypto OR ethereum OR blockchain) after:{(d - timedelta(days=1)):%Y-%m-%d} before:{(d + timedelta(days=1)):%Y-%m-%d}'
        r = get('https://news.google.com/rss/search', timeout=10, params={'q': q, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
        out = []
        for e in (feedparser.parse(r.content).entries if r else [])[:40]:
            ts = e.get('published_parsed')
            if not ts:
                continue
            dt = datetime(*ts[:6], tzinfo=timezone.utc)
            if abs((dt - d).total_seconds()) > 36 * 3600:
                continue
            t = html.unescape(e.get('title', '')); title = t.rsplit(' - ', 1)[0].strip(); src = t.rsplit(' - ', 1)[-1] if ' - ' in t else 'Google News'
            if OTD_JUNK.search(title) or len(title) < 30:
                continue
            sc = sum(p for rx, p in KEYWORDS if re.search(rx, title.lower()))
            out.append({'year': y, 'title': title, 'src': src, 'url': e.get('link', ''), 'sc': sc, 'ts': dt.timestamp()})
        return out
    with ThreadPoolExecutor(8) as ex:
        found = [h for lst in ex.map(year, range(2013, now.year)) for h in lst]
    best, seen = [], []                                              # best story per year, no near-duplicates
    for h in sorted(found, key=lambda h: -h['sc']):
        sig = story_sig(h['title'])
        if h['sc'] < 12 or sum(1 for b in best if b['year'] == h['year']) >= 2 or any(same_story(sig, x) for x in seen):
            continue
        best.append(h); seen.append(sig)
    best = sorted(best[:6], key=lambda h: h['year'])
    r = get('https://api.llama.fi/hacks')
    hacks = sorted([(datetime.fromtimestamp(float(h.get('date', 0)), timezone.utc).year, h) for h in (r.json() if r else [])
                    if (lambda dt: (dt.month, dt.day) == md and dt.year < now.year)(datetime.fromtimestamp(float(h.get('date', 0)), timezone.utc))
                    and float(h.get('amount') or 0) >= 5e6], key=lambda x: -float(x[1].get('amount') or 0))[:3]
    msg, btn, n = f'📜 <b>On this day in crypto · {now:%B %d}</b>\nTap a number → full story post\n', [], 0
    for y, title in FAMOUS.get(md, []):
        n += 1; k = hashlib.md5(f'otd{y}{title}'.encode()).hexdigest()[:12]
        tgs['menu'][k] = {'t': time.time(), 'title': f'{title} ({now:%B %d}, {y})', 'url': '', 'src': 'Crypto history', 'tag': 'TRUE STORY',
                          'story': True, 'facts': f'On {now:%B %d}, {y}: {title}. (Well-documented crypto history.)'}
        msg += f'\n<b>{n}.</b> 📌 <b>{y}</b> · {E(title)}'; btn.append((f'📝 {n}', 'p:' + k))
    for h in best:
        n += 1; k = hashlib.md5(h['url'].encode()).hexdigest()[:12]
        tgs['menu'][k] = {'t': time.time(), 'title': h['title'], 'url': h['url'], 'src': h['src'], 'tag': 'TRUE STORY', 'story': True,
                          'urls': [h['url']], 'facts': f'This happened on {now:%B %d}, {h["year"]} ({now.year - h["year"]} years ago today). '
                                                       f'Headline from that day: {h["title"]} ({h["src"]}).'}
        msg += f'\n<b>{n}.</b> <b>{h["year"]}</b> · {E(h["title"])} <i>({E(h["src"])})</i>'; btn.append((f'📝 {n}', 'p:' + k))
    for y, h in hacks:
        n += 1; hk = hack_item(h, tgs)
        msg += f'\n<b>{n}.</b> 🏴‍☠️ <b>{y}</b> · {E(str(h.get("name")))} hacked for ${float(h.get("amount") or 0)/1e6:,.1f}M'; btn.append((f'📝 {n}', 'p:' + hk['key']))
    unack()
    if n == 0:
        tg(f'📜 Nothing notable found for {now:%B %d}. Try <code>/story Mt Gox</code> to research any story.'); return
    tg(msg[:4000], None, btn[:12])


# ---------------- YouTube Shorts brain: /viral, /hook, weekly report ----------------
PROVEN_HOOKS = [  # starting library until the brain has its own data (common, well-known hook patterns)
    'A number that sounds impossible ("A bug once created 184 billion Bitcoin.")',
    'Start at the twist, then rewind ("He lost $3 billion. It started with one tweet.")',
    'A secret or mystery ("Nobody knows who owns this wallet.")',
    'A direct warning ("If you hold this coin, watch this.")',
    'A villain or conflict ("One man fooled an entire country.")',
    'A question the viewer can\'t ignore ("What happens to your Bitcoin when you die?")']


def cmd_viral(tgs):
    ws = shorts.winners(days=60, k=10)
    if not ws:
        tg('📊 The Shorts brain is still collecting its first data (it runs every morning). Try again tomorrow.'); return
    m = '🔥 <b>Most viral crypto & money Shorts</b> <i>(last 60 days, vs their channel\'s normal)</i>\n'
    btn = []
    for n, (vid, v) in enumerate(ws, 1):
        hook = v.get('an', {}).get('hook')
        m += (f'\n<b>{n}.</b> <a href="https://youtube.com/shorts/{vid}">{E(v["t"][:80])}</a>\n'
              f'    <b>{v["out"]:.0f}x</b> their normal · 👁 {v["views"]:,} · {v["dur"]}s · {E(v["cht"][:30])}'
              + (f'\n    🎣 <i>"{E(hook[:100])}"</i>' if hook else '') + '\n')
        if not v.get('an'):
            btn.append((f'🔍 Why #{n}', f'sw:{vid}'))
    tg(m[:4000], None, btn[:6])


def why_short(vid):
    v = shorts.load()['v'].get(vid)
    if not v:
        tg('That Short is no longer in the data.'); return
    chat_action('typing')
    if not v.get('an') or v['an'].get('fail'):
        a = shorts.gemini_video(vid, [x for x in gemini_models() if 'gemma' not in x][:3])
        if not a:
            tg('⚠️ Gemini couldn\'t watch that one right now. Try again later.'); return
        with shorts.LOCK:
            v['an'] = a
        shorts.save()
    a = v['an']
    tg(f'🔍 <b>{E(v["t"][:90])}</b>\n<b>{v.get("out", 0):.0f}x</b> their channel\'s normal · {v["dur"]}s\n\n'
       f'🎣 <b>Hook:</b> "{E(str(a.get("hook", ""))[:150])}"\n<i>{E(str(a.get("hook_type", "")))} · promise clear by {a.get("hook_seconds", "?")}s</i>\n'
       f'🎭 Tone: {E(str(a.get("tone", "")))} · jokes: {a.get("jokes", "?")} · twist: {"yes" if a.get("twist") else "no"} · ending: {E(str(a.get("ending", "")))}\n'
       f'🎬 {E(str(a.get("visual", ""))[:160])}\n\n💡 <b>Why it works:</b> {E(str(a.get("why", ""))[:250])}')


def cmd_hook(text, tgs):
    """Hook doctor: an idea or a script in -> 5 stronger hooks, ranked, based on real viral hooks."""
    learned = shorts.best_hooks(25)
    ex = ('Real hooks from crypto/money Shorts that beat their channel average (multiplier, hook):\n'
          + '\n'.join(f'- {o:.0f}x: "{h}"' for o, h, t, vw in learned) if len(learned) >= 8
          else 'Proven hook patterns:\n' + '\n'.join('- ' + h for h in PROVEN_HOOKS))
    pat = shorts.patterns()
    if pat:
        ex += '\n\nWhat winners do vs flops: ' + '; '.join(f'{r[0]} {r[1]:.0f}{r[3]} vs {r[2]:.0f}{r[3]}' for r in pat['rows'][:5])
    out = gemini_voice(VOICE + '\nYou write the first line (the hook, said in the first 2-3 seconds) for a faceless crypto story YouTube Short '
                       'on the channel Chain Secrets. Write 5 different hooks for the idea below, strongest first. Each: max 14 words, '
                       'creates curiosity instantly, uses a real number from the idea when there is one, no clickbait lies, no invented facts.\n'
                       'Format exactly:\n1. <hook> | <hook type> | <why it works, max 10 words>\n2. ...\n\n' + ex + '\n\nIDEA OR SCRIPT:\n' + text[:2500])
    rows = [r for r in re.findall(r'(?m)^\s*\d\.\s*(.+)$', out or '')][:5]
    if not rows:
        unack(); tg('⚠️ The AI writer is busy, try again in a minute.'); return
    m = '🎣 <b>Hook doctor</b> · strongest first\n'
    for n, r in enumerate(rows, 1):
        parts = [x.strip() for x in r.split('|')]
        m += f'\n<b>{n}.</b> <code>{E(clean_voice(parts[0]).strip(chr(34)))}</code>' + (f'\n    <i>{E(" · ".join(parts[1:3]))}</i>' if len(parts) > 1 else '')
    m += '\n\n<i>' + ('Based on real viral Shorts from the brain.' if len(learned) >= 8 else 'Based on proven patterns (the brain is still learning).') + '</i>'
    unack(); tg(m)


def shorts_report():
    st = shorts.status(); pat = shorts.patterns(); hooks = shorts.best_hooks(5); ws = shorts.winners(days=7, k=3)
    m = f'🎬 <b>Shorts brain · weekly report</b>\n{st["shorts"]:,} Shorts studied · {st["analyzed"]} watched by AI · {st["winners"]} big winners\n'
    if ws:
        m += '\n🔥 <b>Top Shorts this week</b>\n' + '\n'.join(f'• <a href="https://youtube.com/shorts/{vid}">{E(v["t"][:70])}</a> · <b>{v["out"]:.0f}x</b>' for vid, v in ws) + '\n'
    if hooks:
        m += '\n🎣 <b>Best hooks</b>\n' + '\n'.join(f'• "{E(h[:100])}" <i>({o:.0f}x)</i>' for o, h, t, vw in hooks) + '\n'
    if pat:
        m += f'\n📐 <b>Winners vs flops</b> <i>({pat["n_w"]} vs {pat["n_f"]})</i>\n<pre>' + '\n'.join(
            f'{r[0][:22]:<22}{r[1]:>6.0f}{r[3]:<1} {r[2]:>6.0f}{r[3]}' for r in pat['rows']) + '</pre>'
        m += 'Top hook types: ' + ', '.join(f'{t} ({c})' for t, c in pat['types'])
    else:
        m += '\n<i>Patterns appear once ~8 winners and 8 flops are analyzed.</i>'
    tg(m[:4000])


# ---------------- 🎬 automatic Shorts: /short topic -> script (checkpoint 1) -> voice (2) -> video (3) ----------------
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'studio'))
import story as sstory
TONE_EMO = {'funny': '😂', 'mystery': '🕵️', 'serious': '⚠️', 'hype': '🔥'}
SB_SCHEMA = '''{"outline": ["FIRST plan the script: one short entry per scene = the beat, the real fact it carries, its word budget"],
 "title": "YouTube title, max 60 chars, curiosity, may end with one emoji",
 "alt_hooks": ["3 alternative hook lines"],
 "tone": "funny | mystery | serious | hype",
 "respell": {"HardName": "how to say it", "...": "..."},
 "chart": null OR {"symbol": "BTC", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
 "scenes": [ {"role": "hook|setup|turn|twist|payoff|end", "line": "narration with real digits ($4B, 2017, Oct 25)",
              "hit": "one word from the line where the visual punch lands",
              "beats": [{"word": "a later word in the same line", "text": "MAX 3 WORDS shown on screen", "icon": "optional icon"}],
              "footage": "2-4 word stock video search for the background, e.g. 'prison cell bars' (or empty)",
              "photo": "Wikipedia/Commons search for a REAL photo of the person/place/company, e.g. 'Changpeng Zhao' (or empty)",
              "visual": {"type": "...", ...fields...}} ],
 "description": "2-4 factual sentences with dates and numbers for the YouTube description",
 "hashtags": "6-8 hashtags", "pinned": "a pinned comment question for viewers"}'''
SB_VISUALS = '''Visual types (pick the one that best SHOWS that line):
 title   {"type":"title","text":"MAX 4 BIG WORDS","sub":"optional small line","icon":"optional icon"}
 counter {"type":"counter","value":80000,"prefix":"$","suffix":"","label":"what the number is","icon":"optional icon"}
 stamp   {"type":"stamp","icon":"icon","label":"short caption under the icon","word":"HACKED / GONE / FAKE / ARRESTED...","bad":true}
 person  {"type":"person","name":"FULL NAME","role":"short role/nickname","prop":"none|crown|officer|cuffs"}
 date    {"type":"date","month":"OCT 2017","day":25,"event":"what happened, max 6 words"}
 chart   {"type":"chart","date":"YYYY-MM-DD","label":"OCT 2 · $85 · WHAT HAPPENED"}   (only when "chart" is set; date inside its range)
 versus  {"type":"versus","left":["LABEL","VALUE"],"right":["LABEL","VALUE"],"note":"optional"}
 quote   {"type":"quote","name":"Name","handle":"@handle","text":"exact short quote from the facts","stamp":"optional word"}
 list    {"type":"list","items":["max 3","short","items"]}
Icons: ''' + ', '.join(sstory.ICONS)


def gemini_json(prompt):
    for attempt in range(2):
        for model in [m for m in gemini_models() if 'gemma' not in m][:4]:
            try:
                r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', params={'key': GEMINI}, timeout=60,
                                  json={'contents': [{'parts': [{'text': prompt}]}],
                                        'generationConfig': {'temperature': .8, 'response_mime_type': 'application/json', **think_cfg(model)}})
                if r.status_code == 400 and think_cfg(model):
                    _NOTHINK[model] = False; continue
                if r.ok:
                    txt = ''.join(p.get('text', '') for p in r.json()['candidates'][0]['content']['parts'] if not p.get('thought'))
                    return json.loads(re.search(r'\{.*\}', txt, re.S).group(0))
                print('gemini json', model, r.status_code, r.text[:100])
            except Exception as e:
                print('gemini json fail', model, repr(e)[:100])
        time.sleep(2)
    return None


def short_facts(topic):
    heads = gnews(topic, 15, recent=False)
    heads.sort(key=lambda h: h['ts'])
    lines = [f'- {datetime.fromtimestamp(h["ts"], timezone.utc):%b %d, %Y}: {h["title"]} ({h["src"]})' for h in heads if h['ts']]
    return 'Real headlines about this story (oldest first):\n' + '\n'.join(lines[:15]) if lines else ''


LEN_NAME = {30: '30s', 45: '45s', 60: '1 min', 90: '1.5 min', 120: '2 min'}
LEN_SHAPE = {
    30: 'hook -> setup -> twist -> payoff -> end. One clear story beat per line.',
    45: 'hook -> setup -> turn -> twist -> payoff -> end. Add one vivid detail (a place, an amount, a quote) in the middle.',
    60: 'hook -> setup (who, where) -> turn -> first twist -> a re-hook line around the middle ("But that is not the strangest part.") -> second twist -> payoff -> end.',
    90: 'hook -> setup (who, where, when) -> turn -> first twist -> re-hook around 40% ("But that is not the strangest part.") -> escalation with real numbers -> second twist -> payoff -> end.',
    120: 'cold open hook -> background (who, when, how it started) -> rising stakes with 2-3 concrete events -> re-hook around 40% -> first twist -> '
         'consequences with real numbers -> second twist or reveal -> where it stands today -> end that loops to the hook. Every 10-15 seconds something new must happen.'}


def make_storyboard(topic, facts, tone=None, fix=None, length=45, chart_pref='auto', sett=None):
    sett = sett or {}
    n_sc = str(sett.get('scenes', 'auto'))
    lo_s, hi_s = (int(n_sc), int(n_sc)) if n_sc.isdigit() else sstory.LENGTHS[length][:2]
    pace = sett.get('pace', 'normal')
    beat_rule = {'calm': '1 beat per scene (2 on long lines)', 'fast': '2-3 beats per scene, something new every ~1.5 seconds'}.get(pace, '1-2 beats per scene, something new every ~2 seconds')
    chart_rule = {'off': 'set "chart" to null and use no chart visuals.',
                  'on': 'include a real chart whenever any coin price is part of the story (BTC/ETH/LTC/XRP history works back to 2011). Range = a few weeks around the event.'
                  }.get(chart_pref, 'only if the story is about a crypto price on specific dates (BTC/ETH/LTC/XRP history works back to 2011). Range = a few weeks around the event.')
    cw = 3 if chart_pref == 'off' else 8                                  # call-to-action words added after the story
    lo_w, hi_w, tgt_w = sstory.window(length, cw)
    ww = round(tgt_w / 1.08)                                              # spoken words per written word is about 1.08 ($4.3B -> four point three billion dollars)
    per = max(10, round(ww / max(1, (lo_s + hi_s) / 2)))
    len_rule = (f'a {LEN_NAME[length]} Short must really run {sstory.mmss(sstory.WIN_LO * length)} to {sstory.mmss(sstory.WIN_HI * length)} when spoken. '
                f'That is {lo_w} to {hi_w} spoken words in total (aim for {tgt_w}), so write about {ww} words as written (numbers like $4.3B are said as several words). '
                f'Use {lo_s} to {hi_s} scenes with about {per} words per scene (hook 10 to 14, other lines {max(8, per - 4)} to {per + 5}). '
                'Count your words before answering. A script that is too short is rejected and rewritten.')
    hooks = shorts.best_hooks(15)
    hook_ex = ('Hooks that beat their channel average on real crypto Shorts:\n' + '\n'.join(f'- "{h}" ({o:.0f}x)' for o, h, t, v in hooks)
               if len(hooks) >= 6 else 'Proven hook patterns:\n' + '\n'.join('- ' + h for h in PROVEN_HOOKS))
    pat = shorts.patterns()
    if pat:
        hook_ex += '\nWinners vs flops: ' + '; '.join(f'{r[0]} {r[1]:.0f}{r[3]} vs {r[2]:.0f}{r[3]}' for r in pat['rows'][:6])
    prompt = (f'''You write faceless YouTube Shorts for "Chain Secrets": little-known TRUE crypto & money stories, narrated by a crypto detective,
with a real price chart when the story has one. Write the storyboard for this story as JSON.

HOUSE RULES
- LENGTH: {len_rule} Each line 1-2 short spoken sentences, max 24 words.
- OUTLINE FIRST: fill "outline" before "scenes" (one entry per scene, with its word budget); the scene lines must follow the outline.
- STRUCTURE: {LEN_SHAPE[length]}
- WRITE LIKE A STORYTELLER: concrete names, places, dates and amounts; every line is a punch. Never write vague filler like "faced a crisis",
  "massive", "significant", "shocking", "in the world of crypto". Short sentences. Show, don't summarize.
- Scene 1 (hook): the most shocking fact or the twist FIRST, max 14 words, opens a loop the viewer needs closed. Never start with "Today" or "In this video".
- Middle: every line moves the story. Viewers leave at 13 seconds, so the first twist must come before 20 seconds.
- Last scene (end): a short payoff that loops back to the hook so the replay feels seamless. No call to action (it is added automatically).
- Tone: {('use the tone "' + tone + '".') if tone else 'pick the best one: funny for absurd stories, serious for victims and big losses, mystery for unsolved or secret stories, hype for records.'}
  funny = a light joke every 5-8 seconds; serious = no jokes, respectful; mystery = tension and questions; hype = energy.
- Write numbers with digits in the lines ($4B, 50,000 BTC, 2017, Oct 25). Spell hard names in "respell".
- FACTS: use the facts below and only well-documented facts you are certain of. Never invent numbers, quotes or dates. If unsure, leave it out.
- Chart: {chart_rule}
- "alt_hooks": 3 other strong hook lines for scene 1 (different angles), same rules as the hook.
- MOTION: the screen must never freeze. "hit" is the first punch of a scene; "beats" are extra on-screen moments ({beat_rule}),
  each on a LATER word of the same line than "hit" (a name, number, place or action word), with 1-3 words of on-screen text that ADD info
  (an amount, a place, a date, a nickname), never a copy of the caption.
- "footage": a concrete, filmable stock-video search for the background of that scene (things/places/actions, never a named person: 'courtroom gavel',
  'bitcoin mining farm', 'luxury yacht', 'trading screens red'). "photo": only for a REAL named person, company or place that has a Wikipedia photo.
- No financial advice, no slurs, no claims that real people committed crimes they were not convicted of (say "prosecutors say" when needed).

{SB_VISUALS}

{hook_ex}

FORMAT (JSON only):
{SB_SCHEMA}

STORY: {topic}
{facts}
''' + (f'\nYour previous storyboard had these problems, fix them: {fix}\n' if fix else ''))
    raw = gemini_json(prompt)
    if isinstance(raw, dict):
        raw['length'] = length
    return raw


def fit_length(sb, facts, passes=3):
    """The script is measured with the calibrated speaking rate. Outside the window? Ask for exactly the missing words (or cut the extra),
    re-measure, repeat. Returns the closest version; sb['length_ok'] says whether it made it."""
    best = sb
    for _ in range(passes):
        if best.get('length_ok'):
            return best
        sc = best['scenes']; tgt = best['target_words']
        written = sum(len(x['line'].split()) for x in sc)
        ratio = best['words'] / max(1, written)                           # spoken words per written word in THIS script
        delta = round((tgt - best['words']) / ratio)
        cur = '\n'.join(f'{i + 1}. [{x["role"]}] ({len(x["line"].split())} words, keep the word "{x["hit"]}") {x["line"]}' for i, x in enumerate(sc))
        how = (f'ADD about {delta} words in total. Spread them over the scenes after the hook: more concrete detail (who, where, how much, what happened next) '
               'taken ONLY from the FACTS or from what the lines already say. No filler, no repetition.') if delta > 0 else \
              (f'CUT about {-delta} words in total. Remove the weakest details, never the twist or the numbers.')
        prompt = ('You edit a faceless YouTube Short narration. It is measured by how long it takes to speak. '
                  f'Now: {best["words"]} spoken words = about {sstory.mmss(best["est_secs"])}. Needed: {sstory.window(best["length"], len(sstory.cta(best).split()))[0]} to '
                  f'{sstory.window(best["length"], len(sstory.cta(best).split()))[1]} spoken words (aim {tgt}).\n{how}\n'
                  'Rules: same scenes, same order, same facts and numbers (digits like $4B, 2017); hook max 14 words; every other line max 26 words; '
                  'keep the tone; never invent numbers, names, quotes or dates.\n\nSCRIPT:\n' + cur + '\n\nFACTS you may use:\n' + (facts or '(only well-documented facts already in the script)') +
                  '\n\nReturn JSON only: {"lines": [{"n": 1, "line": "..."}, ...]} with all ' + str(len(sc)) + ' scenes.')
        raw = gemini_json(prompt)
        try:
            new = {x['n']: str(x['line']) for x in raw['lines']}
            if sorted(new) != list(range(1, len(sc) + 1)):
                raise ValueError('lines missing')
            cand = json.loads(json.dumps(best))
            for i, x in enumerate(cand['scenes']):
                x['line'] = new[i + 1]
            cand, _ = sstory.check(cand, strict=False)
        except Exception as e:
            print('fit_length', repr(e)[:100]); continue
        if abs(cand['words'] - tgt) < abs(best['words'] - tgt):
            best = cand
    return best


def draft_check(raw):
    """strict check, but a length-only problem is returned for fit_length() to repair instead of being thrown away"""
    try:
        return sstory.check(json.loads(json.dumps(raw)), strict=True)
    except ValueError as e:
        if str(e).startswith('script is'):
            return sstory.check(json.loads(json.dumps(raw)), strict=False)
        raise


def short_draft(topic, tgs, tone=None, jid=None, length=None, sett=None):
    old = (tgs.get('shorts', {}).get(jid) or {}) if jid else {}
    if not old and jid and os.path.exists(f'jobs/{jid}/storyboard.json'):
        old = {'sb': json.load(open(f'jobs/{jid}/storyboard.json'))}
    facts = old.get('facts')
    length = length or (old.get('sb') or {}).get('length') or 45
    sett = dict(sett or (old.get('sb') or {}).get('settings') or {})
    if facts is None:
        facts = short_facts(topic)
    sb, err, best, note = None, None, None, ''
    for attempt in range(2):                                               # write -> measure -> expand/cut -> measure (never accept a short script silently)
        raw = make_storyboard(topic, facts, tone, err, length, sett.get('chart', 'auto'), sett)
        if isinstance(raw, dict):
            raw['settings'] = dict(sett, length=length)
        if not raw:
            break
        try:
            cand, probs = draft_check(raw)
        except ValueError as e:
            err = str(e); print('storyboard invalid:', err); continue
        cand = fit_length(cand, facts)
        print('draft', attempt, 'words', cand['words'], 'est', cand['est_secs'], 'ok', cand.get('length_ok'))
        if best is None or abs(cand['words'] - cand['target_words']) < abs(best['words'] - best['target_words']):
            best = cand
        if cand.get('length_ok'):
            sb = cand; break
    if not sb and best:                                                    # closest attempt, flagged loudly; the voice is blocked until you choose
        sb = best
        pct = round((sb['est_secs'] / sb['length'] - 1) * 100)
        note = (f'⚠️ <b>Could not reach {LEN_NAME[sb["length"]]}.</b> The best version is about {sstory.mmss(sb["est_secs"])} ({pct:+d}% vs your pick). '
                'I did not accept it silently. Choose: 🔁 Try again, ⏱ another length, edit lines in 🎬 Studio, or ✅ Use anyway.')
    if not sb:
        unack(); tg('⚠️ Couldn\'t write a good script for that story right now' + (f' ({E(err)})' if err else '') + '. Try again, or give a more specific topic.'); return
    if tone:
        sb['tone'] = tone
    if old.get('sb', {}).get('ep'):
        sb['ep'] = old['sb']['ep']                                        # a rewrite keeps its episode number
    jid = jid or hashlib.md5((topic + str(time.time())).encode()).hexdigest()[:8]
    tgs.setdefault('shorts', {})[jid] = {'t': time.time(), 'topic': topic, 'facts': facts, 'sb': sb}
    save_job(jid, sb, 'draft'); studio_index(tgs); git_sync(force=True)
    tgs['shorts'] = dict(sorted(tgs['shorts'].items(), key=lambda kv: -kv[1]['t'])[:10])
    tgs['short_edit'] = jid
    tgs['shorts'][jid]['note'] = note
    unack()
    show_script(jid, tgs)
    studio_button('✏️ To edit every line, visual and setting, tap 🎬 Studio below. It opens this script.', jid)


def vis_txt(v):
    ty = v['type']
    if ty == 'title': return f'big title "{v.get("text", "")}"'
    if ty == 'counter': return f'counter {v.get("prefix", "")}{v.get("value", "")}{v.get("suffix", "")} {v.get("label", "")}'
    if ty == 'stamp': return f'{v.get("icon", "")} + stamp "{v.get("word", "")}"'
    if ty == 'person': return f'person {v.get("name", "")} · {v.get("role", "")}'
    if ty == 'date': return f'calendar {v.get("month", "")} {v.get("day", "")}'
    if ty == 'chart': return f'real chart → {v.get("date", "")} "{v.get("label", "")}"'
    if ty == 'versus':
        L_, R_ = (v.get('left') or ['', ''])[:2], (v.get('right') or ['', ''])[:2]
        return f'versus {" ".join(map(str, L_))} vs {" ".join(map(str, R_))}'
    if ty == 'quote': return f'quote card ({v.get("name", "")})'
    return ty


def show_script(jid, tgs):
    d = tgs['shorts'][jid]; sb = d['sb']
    sb, _ = sstory.check(sb, strict=False); d['sb'] = sb
    ch = sb.get('chart')
    m = (f'🎬 <b>Script</b> · #{next_ep(tgs, peek=True) if not sb.get("ep") else sb["ep"]} {E(sb.get("title", ""))}\n'
         f'{TONE_EMO[sb["tone"]]} {sb["tone"]} · ⏱ {LEN_NAME[sb["length"]]} · {"✅" if sb.get("length_ok") else "⚠️"} ~{sstory.mmss(sb["est_secs"])} ({sb["words"]} words)'
         + (f' · real {ch["symbol"]} chart {ch["start"]} → {ch["end"]}' if ch else '') + '\n')
    for n, s in enumerate(sb['scenes'], 1):
        m += f'\n<b>{n}.</b> <i>{s["role"]}</i> · {E(s["line"])}\n     🎨 {E(vis_txt(s["visual"]))[:90]}'
    m += ('\n\n<b>Checkpoint 1:</b> check the facts. To change a line, reply like <code>3: new line</code>.'
          '\nThen tap ✅ and I record the voice (' + {30: '~12 min', 45: '~15 min', 60: '~20 min', 90: '~28 min', 120: '~35 min'}[sb['length']] + ').')
    if d.get('note'):
        m = m.replace('\n\n<b>Checkpoint 1:</b>', f'\n\n{E(d["note"])}\n\n<b>Checkpoint 1:</b>')
    if not ch:
        m = m.replace('\n\n<b>Checkpoint 1:</b>', '\n\n<i>No chart for this story: the end card skips "every chart hides a story".</i>\n\n<b>Checkpoint 1:</b>')
    blocked = sb.get('length_ok') is False and not sb.get('length_override')
    if blocked and not d.get('note'):
        m = m.replace('\n\n<b>Checkpoint 1:</b>', f'\n\n⚠️ {E(sb.get("length_msg", "length is off"))}\n\n<b>Checkpoint 1:</b>')
    tg(m[:4000], None, ([('🔁 Try again', f'sx:{jid}'), ('✅ Use anyway', f'sk:{jid}')] if blocked else [('✅ Make the voice', f'sa:{jid}'), ('🔄 Rewrite', f'sx:{jid}')]) +
       [(f'{TONE_EMO[t]} {t.title()}', f'st:{jid}:{t}') for t in sstory.TONES if t != sb['tone']] +
       [(('• ' if L == sb['length'] else '') + '⏱ ' + LEN_NAME[L], f'sl:{jid}:{L}') for L in sstory.LENGTHS])


def short_edit(t, tgs):
    """'3: new line' while a script is open -> replace that line and show the script again."""
    jid = tgs.get('short_edit'); d = tgs.get('shorts', {}).get(jid)
    m = re.match(r'^\s*(\d)\s*[:.)\-]\s*(.+)$', t, re.S)
    if not d or not m:
        return False
    n = int(m.group(1)) - 1
    if not 0 <= n < len(d['sb']['scenes']):
        tg(f'There are {len(d["sb"]["scenes"])} lines; send e.g. <code>2: new text</code>.'); return True
    d['sb']['scenes'][n]['line'] = m.group(2).strip()
    try:
        d['sb'], _ = sstory.check(d['sb'], strict=False); d['note'] = ''
    except ValueError as e:
        tg(f'⚠️ {E(e)}'); return True
    show_script(jid, tgs)
    return True


def next_ep(tgs, peek=False):
    """Next channel number: never below 25, never repeats a number already used by an earlier Short."""
    used = [24]
    for f in glob.glob('jobs/*/storyboard.json'):
        try:
            e = int(json.load(open(f)).get('ep') or 0)
            if e < 100: used.append(e)
        except Exception:
            pass
    n = max(max(used), tgs.get('short_ep', 24)) + 1
    if not peek:
        tgs['short_ep'] = n
    return n


def dispatch_short(jid, stage):
    tok, repo = os.environ.get('GH_TOKEN', ''), os.environ.get('GITHUB_REPOSITORY', 'fadishdeed42-spec/chain_radar')
    try:
        r = requests.post(f'https://api.github.com/repos/{repo}/actions/workflows/short.yml/dispatches', timeout=15,
                          headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'},
                          json={'ref': 'main', 'inputs': {'job': jid, 'stage': stage}})
        return r.status_code == 204
    except Exception as e:
        print('dispatch fail', e); return False


def short_approve(jid, tgs, seed_bump=False):
    d = tgs.get('shorts', {}).get(jid)
    path = f'jobs/{jid}/storyboard.json'
    if d:
        sb = d['sb']
    elif os.path.exists(path):
        sb = json.load(open(path))
    else:
        git_sync(force=True)
        if not os.path.exists(path):
            tg('That Short is too old. Start again with /short.'); return
        sb = json.load(open(path))
    if sb.get('length_ok') is False and not sb.get('length_override') and not seed_bump:      # never spend 20 minutes of voice on a script that is the wrong length
        tg('⚠️ <b>This script is the wrong length.</b> ' + E(sb.get('length_msg', '')) + '\nFix it in 🎬 Studio, try again, or accept it knowingly.', None,
           [('🔁 Try again', f'sx:{jid}'), ('✅ Use anyway', f'sk:{jid}')]); return
    if seed_bump:
        sb['voice_seed'] = int(sb.get('voice_seed', 7)) + 11
    if not sb.get('ep'):
        sb['ep'] = next_ep(tgs)
    save_job(jid, sb, 'voice_running')
    if d: d['sb'] = sb
    studio_index(tgs); git_sync(force=True)
    if dispatch_short(jid, 'voice'):
        mins = {30: '12', 45: '15', 60: '20', 90: '28', 120: '35'}.get(sstory.length_of(sb), '15')
        tg('🎙 Recording the voice' + (' (new take)' if seed_bump else '') + f' for #{sb["ep"]}. You\'ll get an audio preview here in ~{mins} minutes.')
    else:
        tg('⚠️ Couldn\'t start the voice job on GitHub. Try again in a minute.')


def short_render(jid, tgs=None):
    git_sync(force=True)
    if not os.path.exists(f'jobs/{jid}/voicep_words.srt'):
        tg('🎙 Record the voice first (✅ Make the voice), then make the video.'); return
    job_status(jid, 'rendering')
    if tgs is not None: studio_index(tgs)
    git_sync(force=True)
    if dispatch_short(jid, 'render'):
        tg('🎬 Making the video: real chart, animation, sound and mix. It arrives here in ~10–20 minutes.')
    else:
        tg('⚠️ Couldn\'t start the video job on GitHub. Try again in a minute.')


def short_reedit(jid, tgs):
    if jid not in tgs.get('shorts', {}):
        git_sync(force=True)
        p = f'jobs/{jid}/storyboard.json'
        if not os.path.exists(p):
            tg('That Short is too old. Start again with /short.'); return
        tgs.setdefault('shorts', {})[jid] = {'t': time.time(), 'topic': json.load(open(p)).get('title', ''), 'facts': '', 'sb': json.load(open(p))}
    tgs['short_edit'] = jid
    show_script(jid, tgs)


# ---------------- 🎬 Studio Mini App: jobs on disk, library index, actions sent from the app ----------------
STUDIO_URL = 'https://fadishdeed42-spec.github.io/chain_radar/studio/'


def job_status(jid, state=None, **kw):
    p = f'jobs/{jid}/status.json'
    try:
        st = json.load(open(p))
    except Exception:
        st = {}
    if state:
        st.update({'state': state, 't': int(time.time()), **kw})
        if state in ('draft', 'voice_running', 'rendering'):
            st.pop('error', None)
        os.makedirs(f'jobs/{jid}', exist_ok=True)
        json.dump(st, open(p, 'w'))
    return st


def save_job(jid, sb, state=None):
    os.makedirs(f'jobs/{jid}', exist_ok=True)
    json.dump({k: v for k, v in sb.items() if not k.startswith('_')}, open(f'jobs/{jid}/storyboard.json', 'w'), indent=1)
    if state or not os.path.exists(f'jobs/{jid}/status.json'):
        job_status(jid, state or 'draft')


def studio_index(tgs):
    """state/studio.json: what the Studio app lists (jobs + live status) and suggests (ideas)."""
    jobs = {}
    for f in glob.glob('jobs/*/storyboard.json'):
        jid = f.split('/')[1]
        try:
            sb = json.load(open(f)); st = job_status(jid)
        except Exception:
            continue
        jobs[jid] = {'ep': sb.get('ep'), 'title': sb.get('title', ''), 'length': sb.get('length', 45), 'tone': sb.get('tone', ''),
                     'state': st.get('state', 'draft'), 't': st.get('t') or int(os.path.getmtime(f))}
    ideas = []
    try:
        s = load_state()
        for k, sc, age, ns in (s.get('top') or [])[:6]:
            it = s.get('menu', {}).get(k)
            if it and not junk_story(it['title'], [{'title': it['title'], 'src': it.get('src', '')}], it.get('coin')):
                ideas.append({'title': it['title'], 'kind': f'📰 news · {ns} sources'})
    except Exception:
        pass
    now = datetime.now(timezone.utc)
    for y, title in FAMOUS.get((now.month, now.day), []):
        ideas.append({'title': f'{title} ({y})', 'kind': '📜 on this day'})
    for vid, v in shorts.winners(days=30, k=3):
        ideas.append({'title': v['t'][:90], 'kind': f'🔥 viral Short · {v["out"]:.0f}x'})
    rs = [(os.path.getmtime(d + '/voicep_words.srt'), r) for d in glob.glob('jobs/*') for r in [sstory.measured_rate(d)] if r]
    rs = [r for _, r in sorted(rs)[-8:]]
    rate_ = round(sorted(rs)[len(rs) // 2], 3) if rs else sstory.RATE_DEFAULT      # median speaking rate of the real voices (calibrates every length estimate)
    idx = {'jobs': jobs, 'ideas': ideas[:12], 'next_ep': next_ep(tgs, peek=True), 'rate': rate_, 'updated': int(time.time())}
    os.makedirs('state', exist_ok=True)
    json.dump(idx, open('state/studio.json', 'w'), separators=(',', ':'))
    return idx


def studio_button(text, jid=None):
    """Send a message with the menu keyboard whose 🎬 Studio button opens this job directly."""
    send_menu(text, job=jid)


def decode_app(data):
    import base64, zlib
    if data.startswith('z:'):
        data = zlib.decompress(base64.b64decode(data[2:]), -15).decode()
    return json.loads(data)


def app_action(data, tgs):
    try:
        p = decode_app(data)
    except Exception as e:
        tg(f'⚠️ The Studio sent something I could not read ({E(repr(e)[:80])}). Try again.'); return
    a, jid = p.get('a'), p.get('id')
    sett = {k: v for k, v in (p.get('settings') or {}).items() if k in sstory.DEFAULTS}
    if a == 'new':
        L = int(sett.get('length') or 45)
        tone = sett.get('tone') if sett.get('tone') in sstory.TONES else None
        ack(f'⏳ Researching and writing a {LEN_NAME.get(L, str(L) + "s")} script…')
        short_draft(p.get('topic', '')[:300], tgs, tone, None, L, sett)
        return
    if not jid or not re.match(r'^[a-z0-9]{4,16}$', jid):
        tg('⚠️ That Short has no id. Open it again from the 📚 Library.'); return
    if a == 'render':
        short_render(jid, tgs); return
    if a == 'rewrite':
        d_ = tgs.get('shorts', {}).get(jid) or {}
        topic = d_.get('topic') or (json.load(open(f'jobs/{jid}/storyboard.json')).get('title') if os.path.exists(f'jobs/{jid}/storyboard.json') else '')
        if not topic:
            tg('That Short is too old to rewrite. Start a new one.'); return
        tone = p.get('tone') if p.get('tone') in sstory.TONES else None
        ack('⏳ Rewriting the script…')
        short_draft(topic, tgs, tone, jid, int(p.get('length') or 45), sett)
        return
    sb = p.get('sb')
    if not isinstance(sb, dict):
        tg('⚠️ The Studio did not send the script. Try again.'); return
    try:
        sb, probs = sstory.check(sb, strict=False)
    except ValueError as e:
        tg(f'⚠️ The script needs a fix before I can use it: {E(e)}'); return
    old = tgs.setdefault('shorts', {}).setdefault(jid, {'t': time.time(), 'topic': sb.get('title', ''), 'facts': ''})
    old.update({'sb': sb, 't': time.time(), 'note': ''})
    tgs['short_edit'] = jid
    if a == 'save':
        save_job(jid, sb, 'draft'); studio_index(tgs); git_sync(force=True)
        tg(f'💾 Saved <b>#{sb.get("ep") or next_ep(tgs, peek=True)} {E(sb.get("title", ""))}</b> · ~{sb["est_secs"]}s, {len(sb["scenes"])} scenes'
           + ('\n⚠️ ' + E('; '.join(probs)) if probs else ''))
    elif a == 'voice':
        if p.get('force'):
            sb['length_override'] = True
            tgs['shorts'][jid]['sb'] = sb
        short_approve(jid, tgs)
    elif a == 'retake':
        short_approve(jid, tgs, seed_bump=True)


HELP = ('🕵️ <b>Chain Radar</b>\n\n'
        '<b>Find stories</b>\n'
        '/top — hottest crypto stories right now → tap one for a full post\n'
        '/movers — biggest gainers & losers + why they moved\n'
        '/hacks — biggest hacks of the last 30 days\n'
        '/story — on this day in crypto (real prices & hacks)\n'
        '/brain — what the learning brain knows so far\n'
        '/short <i>story</i> — a finished YouTube Short in your style (script → voice → video)\n'
        '/viral — most viral crypto Shorts right now + why they worked\n'
        '/hook <i>idea</i> — 5 stronger hooks for your next Short\n'
        '/story <i>topic</i> — research a story, e.g. <code>/story Do Kwon</code> → thread + Shorts script\n\n'
        '<b>Replies</b>\n'
        '• <b>Share any X post link</b> to me → 3 ready replies (fact, witty, chart + image)\n'
        '• Viral stories come with a 🔥 reply-window alert + ready replies\n\n'
        '<b>Make posts from anything</b>\n'
        '• <b>Forward</b> any news message from another channel to me → full post\n'
        '• <b>Paste a link</b> to any article → full post\n'
        '• <b>Type any coin</b> (<code>$PEPE</code>, <code>chart sol</code>) → real chart + a ready sentence\n\n'
        '<b>Alerts</b>\n'
        '/mute 3 — pause alerts for 3 hours · /unmute')
COMMANDS = [('top', 'Hottest stories now'), ('movers', 'Gainers & losers + why'), ('hacks', 'Biggest hacks (30 days)'),
            ('reply', 'Replies for an X post: /reply <link>'), ('story', 'On this day / research: /story Do Kwon'), ('chart', 'Candle chart: /chart BTC 7d'),
            ('short', 'Make a YouTube Short: /short story'), ('kit', 'Today\'s posting kit'), ('viral', 'Most viral crypto Shorts'), ('hook', 'Hook doctor: /hook idea'), ('brain', 'Learning brain status'), ('mute', 'Pause alerts: /mute 3'), ('unmute', 'Resume alerts'), ('help', 'How to use the bot')]


def gnews(q, n=8, recent=True):
    r = get('https://news.google.com/rss/search', timeout=10,
            params={'q': q + (' when:2d' if recent else ''), 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
    out = []
    for e in (feedparser.parse(r.content).entries if r else [])[:n]:
        t = html.unescape(e.get('title', '')); ts = e.get('published_parsed')
        out.append({'title': t.rsplit(' - ', 1)[0], 'src': t.rsplit(' - ', 1)[-1] if ' - ' in t else 'Google News',
                    'url': e.get('link', ''), 'ts': time.mktime(ts) - time.timezone if ts else 0})
    return out


def ago(ts):
    m = (time.time() - ts) / 60
    return f'{m:.0f}m ago' if m < 90 else f'{m/60:.0f}h ago' if m < 2880 else datetime.fromtimestamp(ts, timezone.utc).strftime('%b %d, %Y')


def cmd_chart(args):
    sym = (args[0] if args else 'BTC').upper().lstrip('$'); span = args[1].lower() if len(args) > 1 and args[1].lower() in SPANS else '1d'
    h = cg_search(sym, strict=False)
    coin = coin_by_id(h['id']) if h else None
    if not coin:
        tg(f'Couldn\'t find a coin called {E(sym)}.'); return
    send_coin_chart(coin, span)


def send_coin_chart(coin, span='1d'):
    lab = SPANS[span][3].split(' · ')[0]
    img = coin_card(coin, f'{coin["name"]}: the last {lab}' if span != '1d' else f'{coin["name"]} in the last 24 hours', span,
                    {'8h': '8H CHART', '1d': '24H CHART', '7d': '7D CHART', '30d': '30D CHART', '1y': '1Y CHART'}[span])
    if not img:
        tg('No candle data for that coin right now.'); return
    tg(f'📈 <b>{E(coin["name"])} ({coin["sym"]})</b> · {fmt_p(coin["price"])} · {coin["h24"]:+.1f}% 24h', img,
       [(x.upper(), f'c:{coin["id"]}:{x}') for x in ('1d', '7d', '30d', '1y') if x != span])


def cmd_hacks(tgs):
    r = get('https://api.llama.fi/hacks')
    hs = sorted([h for h in (r.json() if r else []) if NOW - float(h.get('date', 0)) < 30 * 86400],
                key=lambda h: -float(h.get('amount') or 0))[:6]
    if not hs:
        tg('No hacks logged in the last 30 days (DefiLlama).'); return
    msg, btn = '🏴‍☠️ <b>Biggest hacks · last 30 days</b> <i>(DefiLlama)</i>\n', []
    for n, h in enumerate(hs, 1):
        hk = hack_item(h, tgs)
        msg += f'\n<b>{n}.</b> {E(str(h.get("name")))} · <b>${float(h.get("amount") or 0)/1e6:,.1f}M</b> · {hk["hack"]["date"]} · {E(hk["hack"]["method"])}'
        btn.append((f'📝 {n}', 'p:' + hk['key']))
    tg(msg + '\n\nTap a number → HACKED card + full post', None, btn)


def hack_item(h, tgs):
    amt = float(h.get('amount') or 0); when = datetime.fromtimestamp(float(h['date']), timezone.utc).strftime('%b %d, %Y')
    k = hashlib.md5(f'{h.get("name")}{h.get("date")}'.encode()).hexdigest()[:12]
    it = {'t': NOW, 'key': k, 'title': f'{h.get("name")} hacked for ${amt/1e6:,.1f} million', 'url': '', 'src': 'DefiLlama', 'tag': 'HACK',
          'hack': {'amount': card.big_money(f'${amt:,.0f}'), 'chain': str(h.get('chain') or (h.get('chains') or [''])[0] or ''),
                   'method': str(h.get('technique') or h.get('classification') or 'Unknown')[:28], 'date': when},
          'facts': f'Hack date: {when}. Protocol: {h.get("name")}. Chain: {h.get("chain") or h.get("chains")}. Method: {h.get("technique") or h.get("classification")}. Amount stolen: ${amt:,.0f}. (DefiLlama hacks database.)'}
    tgs['menu'][k] = it
    return it


def research_story(topic):
    tg(f'🔎 Researching <b>{E(topic)}</b> from real headlines…')
    heads = gnews(topic, 15, recent=False)
    if not heads:
        tg('No news found for that topic. Try a different name.'); return
    heads.sort(key=lambda h: h['ts'])
    facts = 'Real headlines about this story, oldest first (only use what they say):\n' + '\n'.join(
        f'- {datetime.fromtimestamp(h["ts"], timezone.utc):%b %d, %Y}: {h["title"]} ({h["src"]})' for h in heads if h['ts'])
    make_post({'title': topic, 'facts': facts, 'src': 'Google News', 'tag': 'TRUE STORY', 'story': True, 'url': heads[-1]['url']})


def handle(u, tgs):
    cb, msg = u.get('callback_query'), u.get('message')
    who = str((cb or msg or {}).get('from', {}).get('id', ''))
    if CHAT and who != str(CHAT):
        return                                          # only obey the owner
    if cb:
        data = cb.get('data') or ''
        toast = 'Refreshing…' if data == 'mr:' else 'On it…'
        if data.startswith('f:'):
            _, k, val = data.split(':', 2); toast = on_feedback(k, val, tgs)
        elif data.startswith('ps:'):
            toast = 'Logged ✅'
        try:
            requests.post(f'https://api.telegram.org/bot{TOKEN}/answerCallbackQuery', data={'callback_query_id': cb['id'], 'text': toast}, timeout=10)
        except Exception:
            pass
        mid = (cb.get('message') or {}).get('message_id')
        if data.startswith('f:'):
            return
        if data.startswith('ps:'):
            on_posted(data[3:]); return
        if data.startswith('p:'):
            item = menu_item(data[2:], tgs)
            if item:
                ack()
                try:
                    make_post(item)
                finally:
                    unack()
            else:
                tg('That story expired. Send /top for the current list.')
        elif data.startswith('v:'):
            _, k, vis = data.split(':', 2)
            switch_design(k, vis, (cb.get('message') or {}).get('message_id'))
        elif data.startswith('ra:'):
            parts = data.split(':'); keep = len(parts) > 3                  # ':k' = switching side: keep the old reply message
            if keep:
                r = tgs.get('replies', {}).get(parts[1])
                if r:
                    r['stance'] = parts[2]; ack('⏳ Writing your reply…'); reply_from_text(r['text'], r['author'], r.get('post'), tgs, parts[1], parts[2])
            else:
                on_stance(parts[1], parts[2], tgs, mid)
        elif data.startswith('sa:'):
            short_approve(data[3:], tgs)
        elif data.startswith('sk:'):                                     # explicit consent to a script outside the length window
            d_ = tgs.get('shorts', {}).get(data[3:])
            if d_:
                d_['sb']['length_override'] = True; d_['note'] = ''; save_job(data[3:], d_['sb'], 'draft')
            short_approve(data[3:], tgs)
        elif data.startswith('sx:'):
            d_ = tgs.get('shorts', {}).get(data[3:])
            if d_: ack('⏳ Rewriting…'); short_draft(d_['topic'], tgs, None, data[3:])
        elif data.startswith('st:'):
            _, jid_, tone_ = data.split(':', 2); d_ = tgs.get('shorts', {}).get(jid_)
            if d_: ack(f'⏳ Rewriting as {tone_}…'); short_draft(d_['topic'], tgs, tone_, jid_)
        elif data.startswith('sl:'):
            _, jid_, L_ = data.split(':', 2); d_ = tgs.get('shorts', {}).get(jid_)
            if d_: ack(f'⏳ Rewriting as a {LEN_NAME[int(L_)]} Short…'); short_draft(d_['topic'], tgs, d_['sb'].get('tone'), jid_, int(L_))
        elif data.startswith('sv:'):
            short_render(data[3:], tgs)
        elif data.startswith('sr:'):
            short_approve(data[3:], tgs, seed_bump=True)
        elif data.startswith('se:'):
            short_reedit(data[3:], tgs)
        elif data.startswith('sw:'):
            why_short(data[3:])
        elif data == 'kq:':
            kit_take(tgs)
        elif data.startswith('rf:'):
            on_reply_feedback(data)
        elif data.startswith('rr:'):
            more_replies(data[3:], tgs)
        elif data.startswith('x:'):
            _, k, what = data.split(':', 2)
            send_extra(k, what)
        elif data == 'r:':
            live_top(tgs)
        elif data.startswith('m:'):
            chat_action(); coin_view('id:' + data[2:], tgs)
        elif data == 'mr:':
            cmd_movers(tgs, mid)
        elif data.startswith('cw:'):
            _, k, w = data.split(':', 2); coin_switch(k, w, tgs, mid)
        elif data.startswith('cs:'):
            coin_resentence(data[3:], tgs, mid)
        elif data.startswith('cp:'):
            ack(); coin_fullpost(data[3:], tgs)
        elif data.startswith('c:'):
            _, cid, span = (data.split(':') + ['1d'])[:3]
            coin = coin_by_id(cid)
            if coin:
                send_coin_chart(coin, span if span in SPANS else '1d')
        return
    msg = msg or {}
    if msg.get('web_app_data'):                                          # an action sent from the 🎬 Studio Mini App
        app_action(msg['web_app_data'].get('data', ''), tgs); return
    t = (msg.get('text') or msg.get('caption') or '').strip()
    if not t:
        return
    parts = t.split(); c = parts[0].lower().split('@')[0]; args = parts[1:]
    fwd = msg.get('forward_origin') or {}
    fwd_src = (fwd.get('chat') or {}).get('title') or (fwd.get('sender_user') or {}).get('first_name') or fwd.get('sender_user_name')
    MAP = {'📋 Today\'s kit': '/kit', '🧠 Brain': '/brain', '📰 Top stories': '/top', '📊 Movers': '/movers', '🏴‍☠️ Hacks': '/hacks', '📖 Story': '/story', '🧠 Brain': '/brain'}
    if t in MAP:
        c, args = MAP[t], []
    if tgs.get('short_edit') and re.match(r'^\s*\d\s*[:.)\-]\s*\S', t) and short_edit(t, tgs):
        return
    if t in ('🎬 Make a Short', '🎬 Studio'):
        tg('🎬 Send <code>/short</code> + any crypto or money story, e.g. <code>/short QuadrigaCX</code>. '
           'Choose the length: <code>/short 30 …</code>, <code>/short 1min …</code>, <code>/short 2min …</code> (default 45s), or change it later with the ⏱ buttons.'); return
    if t == '💬 Reply to a post':
        tg('💬 Share or paste the X post link here and I\'ll write the best reply.'); return
    if c in ('/start', '/help', 'help'):
        tg(HELP); send_menu()
    elif c == '/brain':
        brain_status()
    elif c == '/ep':
        if args and args[0].isdigit():
            tgs['short_ep'] = int(args[0]) - 1; tg(f'✅ The next Short will be <b>#{int(args[0])}</b>.')
        else:
            tg(f'The next Short will be <b>#{next_ep(tgs, peek=True)}</b>. Change it with <code>/ep 30</code>.')
    elif c == '/short':
        L, rest, skip = 45, [], False
        for a in args:
            if skip and a.lower() in ('s', 'sec', 'secs', 'seconds', 'm', 'min', 'mins', 'minute', 'minutes'):
                skip = False; continue
            skip = False
            m_ = re.match(r'^(\d+)\s*(s|sec|secs|m|min|mins)?$', a.lower())
            if m_ and not rest or m_ and m_.group(2):
                v_ = int(m_.group(1)) * (60 if (m_.group(2) or '').startswith('m') else 1)
                if v_ in (1, 2): v_ *= 60
                if 20 <= v_ <= 180: L = min(sstory.LENGTHS, key=lambda k: abs(k - v_)); skip = True; continue
            rest.append(a)
        if rest:
            ack(f'⏳ Researching the story and writing a {LEN_NAME[L]} script…'); short_draft(' '.join(rest), tgs, None, None, L)
        else:
            tg('🎬 Send <code>/short</code> + a story, e.g. <code>/short Mt Gox collapse</code>. Add a length: <code>/short 30 Bitcoin pizza</code>, '
               '<code>/short 1min FTX</code>, <code>/short 2min Silk Road</code> (default 45s).')
    elif c == '/viral':
        cmd_viral(tgs)
    elif c == '/hook':
        if args:
            ack('⏳ Writing hooks…'); cmd_hook(' '.join(args), tgs)
        else:
            tg('🎣 Send <code>/hook</code> + your Short idea or script, e.g. <code>/hook Mt Gox lost 850,000 bitcoin</code>')
    elif c == '/kit':
        ack('⏳ Building today\'s kit…'); daily_kit(tgs); unack()
    elif c in ('/top', 'top', 'news'):
        if not send_cached_top():
            live_top(tgs)
    elif c == '/chart':
        if args and args[0].lower() not in SPANS:
            ack(f'⏳ Pulling the {args[0].upper()} chart…'); coin_view(args[0], tgs)
        else:
            cmd_chart(args)
    elif c == '/reply':
        if args and XLINK.search(args[0]):
            cmd_reply(args[0], tgs)
        elif args:
            ask_stance(' '.join(args), 'someone', None, tgs, hashlib.md5(t.encode()).hexdigest()[:10])
        else:
            tg('Send <code>/reply</code> + an X post link — or just paste/share the link to me.')
    elif XLINK.search(t) and not fwd:
        cmd_reply(XLINK.search(t).group(0), tgs)
    elif not fwd and len(t) <= 40 and coin_query(t):
        q = coin_query(t); ack(f'⏳ Pulling the {q.upper()} chart…'); coin_view(q, tgs)
    elif c == '/movers':
        cmd_movers(tgs)
    elif c == '/hacks':
        cmd_hacks(tgs)
    elif c == '/story':
        research_story(' '.join(args)) if args else on_this_day(tgs)
    elif c == '/mute':
        hrs = float(args[0]) if args and re.match(r'^\d+(\.\d+)?$', args[0]) else 3
        tgs['mute_until'] = NOW + hrs * 3600; tg(f'🔕 Alerts paused for {hrs:g}h. /unmute to resume.')
    elif c == '/unmute':
        tgs['mute_until'] = 0; tg('🔔 Alerts back on.')
    elif c.startswith('/'):
        tg(HELP)
    elif fwd or len(t) >= 60 or re.match(r'https?://', t) or c == '/post':
        urls = re.findall(r'https?://\S+', t)
        if re.match(r'https?://\S+$', t):               # just a link
            url = t
            ack()
            pg = get(url, timeout=8); ttl = re.search(r'(?is)<title[^>]*>(.*?)</title>', pg.text) if pg else None
            ttl = html.unescape(ttl.group(1)).split(' | ')[0].split(' - ')[0].strip() if ttl else url
            make_post({'title': ttl, 'url': url, 'src': re.sub(r'^https?://(www\.)?([^/]+).*', r'\2', url), 'urls': [url]})
        else:                                            # forwarded or pasted news text
            ack()
            first = re.split(r'(?<=[.!?])\s|\n', re.sub(r'https?://\S+', '', t).strip())[0][:140]
            make_post({'title': first or t[:120], 'facts': 'News text (from a Telegram message):\n' + t[:3000], 'src': fwd_src or 'Telegram',
                       'url': urls[0] if urls else '', 'urls': urls[:2]})
    else:
        tg(HELP)


def listen(seconds=int(os.environ.get('LISTEN_SECONDS', 20400))):
    """Long-poll Telegram for hours (GitHub allows 6h jobs) so every tap/command is answered in seconds."""
    global TGS
    tgs = load_tg(); TGS = tgs
    try:
        requests.post(f'https://api.telegram.org/bot{TOKEN}/setMyCommands', timeout=10,
                      data={'commands': json.dumps([{'command': a, 'description': b} for a, b in COMMANDS])})
    except Exception:
        pass
    import threading
    end = time.time() + seconds; last_save = time.time(); last_scan = 0; scan_t = [None]

    def safe_scan():
        try:
            main()
        except Exception as e:
            print('scan fail', repr(e))
    if tgs.get('menu_v') != MENU_V:
        tgs['menu_v'] = MENU_V; save_tg(tgs)
        send_menu('🆕 Chain Secrets Studio is here\n\n'
                  '• Tap 🎬 Studio below: write, edit and render Shorts with all the settings\n'
                  '• Length, tone, chart, voice energy, pauses, captions, motion, music, sound effects, end card\n'
                  '• Library with every Short and its status\n'
                  '• /short still works in the chat')
    while time.time() < end - 5:
        global NOW
        NOW = time.time()
        try:
            scheduler(tgs)
        except Exception as e:
            print('scheduler fail', repr(e))
        if time.time() - last_scan > 300 and not (scan_t[0] and scan_t[0].is_alive()):   # news + movers scan every 5 min
            last_scan = time.time(); scan_t[0] = threading.Thread(target=safe_scan, daemon=True); scan_t[0].start()
        try:
            r = requests.get(f'https://api.telegram.org/bot{TOKEN}/getUpdates', timeout=40,
                             params={'offset': tgs.get('offset', 0) + 1, 'timeout': int(min(25, max(1, end - time.time() - 5)))})
            ups = r.json().get('result', []) if r.ok else []
            if r.status_code == 409:                      # another listener is running; let it work
                print('another listener active, exiting'); return
        except Exception as e:
            print('poll fail', e); time.sleep(3); continue
        for u in ups:
            NOW = time.time()
            tgs['offset'] = max(tgs.get('offset', 0), u['update_id'])
            save_tg(tgs)
            try:
                handle(u, tgs)
            except Exception as e:
                print('handle fail', repr(e)); tg('⚠️ Something went wrong with that request. Try again.')
            save_tg(tgs)
        if time.time() - last_save > 600:
            save_tg(tgs); git_sync(force=True)
            try:
                studio_index(tgs); git_sync(force=True)                  # library statuses (jobs finished on GitHub)
            except Exception as e:
                print('studio index fail', repr(e))
            last_save = time.time()
    save_tg(tgs)


if __name__ == '__main__':
    mode = sys.argv[1] if sys.argv[1:] else 'scan'
    if mode == 'listen':
        listen()
    elif mode == 'selftest':                  # silent: renders to state/selftest/ instead of Telegram
        os.makedirs('state/selftest', exist_ok=True); n = [0]

        def fake_tg(text, photo=None, buttons=None):
            n[0] += 1
            open(f'state/selftest/{n[0]:02d}.txt', 'w').write(text + '\n\nBUTTONS: ' + str(buttons))
            if photo:
                open(f'state/selftest/{n[0]:02d}.png', 'wb').write(photo)
        globals()['tg'] = fake_tg
        globals()['ack'] = lambda *a, **k: None; globals()['unack'] = lambda: None; globals()['chat_action'] = lambda *a: None
        t = {'menu': {}}
        n_new = shorts.collect(4)                                         # live check: YouTube key + quota
        models = [m for m in gemini_models() if 'gemma' not in m][:3]
        n_an = shorts.analyze_batch(4, models)                              # live check: Gemini can watch YouTube Shorts
        fake_tg(f'SHORTS status {shorts.status()} new={n_new} analyzed={n_an}')
        sample = [(k, v) for k, v in shorts.load()['v'].items() if v.get('an')][:3]
        fake_tg('SHORTS sample analyses\n' + json.dumps([{'t': v['t'], 'out': v.get('out'), 'an': v['an']} for k, v in sample], indent=1)[:3500])
        cmd_viral(t); cmd_hook('Mt Gox lost 850,000 bitcoin in 2014 and users waited 10 years to get paid back', t)
        print('beirut now', datetime.now(BEIRUT), 'quiet', quiet())
        st = load_state()
        for k, it in list(st.get('menu', {}).items())[:40]:
            if it.get('coin') and it.get('t0'):
                c = coin_by_id(it['coin']); img = coin_card(c, it['title'], event_ts=it['t0'])
                fake_tg('EVENT CHART ' + it['title'], img); break
    elif mode == 'test':                      # full post for the current #1 story (end-to-end check)
        m, n = collect_market(), collect_news()
        (sc, lead, coin, srcs, age), g = sorted([(score_group(g, m, []), g) for g in cluster(n)], key=lambda x: -x[0][0])[0]
        st = load_state(); k = remember(st, g, lead, coin, srcs)
        tg('🧪 Test post for the #1 story right now:'); make_post(st['menu'][k])
    else:
        main()
