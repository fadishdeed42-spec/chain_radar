"""Chain Radar — finds crypto stories that are about to go viral and pings Telegram.
Runs every 15 min on GitHub Actions. Free sources only. State in state/seen.json.
Env: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (required), GEMINI_API_KEY (optional, for drafts)."""
import os, re, json, time, html, hashlib, io, sys
from datetime import datetime, timezone
import requests, feedparser
import brain

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
    base = f'⚡ {headline}' + (f'\n\n{coin["sym"]}: ${coin["price"]:,.6g} ({coin["h24"]:+.1f}% 24h)' if coin else '')
    out = gemini(STYLE + 'Write ONE X post (max 260 characters) with a strong hook. Reply with the post text only.\n\nFACTS:\n'
                 f'Headline: {headline}\nSources: {", ".join(list(srcs)[:4])}\n'
                 + (f'Price: {coin["name"]} ${coin["price"]:,.6g}, {coin["h24"]:+.1f}% in 24h, {coin["h1"]:+.1f}% in 1h\n' if coin else ''))
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


def quiet(now=None):
    """1:00-9:00 Beirut (22:00-06:00 UTC): only huge news gets through."""
    h = datetime.fromtimestamp(now or time.time(), timezone.utc).hour
    return h >= 22 or h < 6


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

    # 3) breaking news: only strong stories never sent before (any outlet)
    for (sc, lead, coin, srcs, age), g in scored:
        pr = probs.get(key_of(g))
        strong = (sc >= ALERT and (pr is None or pr >= 0.5)) or (pr is not None and pr >= 0.8)
        if not strong:
            continue
        urls = [i['url'] for i in g['items']]
        if is_dup(st, lead['title'], urls):
            continue
        mark_sent(st, lead['title'], urls)
        viral = (pr is not None and pr >= 0.85) or (pr is None and (sc >= VIRAL or (len(srcs) >= 4 and age < 1.5)))
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
    return f'${v:,.0f}' if v >= 1000 else f'${v:,.2f}' if v >= 1 else f'${v:.4g}'


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
    sh('git add state/tg.json state/seen.json state/listen.log state/brain.json state/model.json 2>/dev/null; git commit -qm "listen state [skip ci]"')
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


def _candles(coin, span='1d', event_ts=None):
    """Real OHLCV. With event_ts the window is built around the news (some time before, everything after).
    Coinbase first (has volume, checked against CoinGecko price), CoinGecko OHLC fallback. Returns (rows, source, label)."""
    now = time.time()
    if event_ts and 0 < now - event_ts < 120 * 86400:
        age = now - event_ts
        total = max(age * 1.6, 3 * 3600)
        gran = next(g for g in (300, 900, 3600, 21600, 86400) if total / g <= 95 or g == 86400)
        start = max(event_ts - max(total - age, 4 * gran), now - 290 * gran)
        rows = coinbase(coin['sym'], gran, start, now)
        lab = f'{GRAN_LABEL[gran]} candles · around the news'
        n_days = 1 if total <= 86400 else 7 if total <= 7 * 86400 else 30 if total <= 30 * 86400 else 90
    else:
        gran, n, n_days, lab = SPANS[span]
        rows = coinbase(coin['sym'], gran)[-n:]
        start = 0
    if len(rows) >= 20 and (not coin.get('price') or abs(rows[-1][4] / coin['price'] - 1) < 0.15):
        return rows, 'Coinbase', lab
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
         'say "reportedly" when the source is unsure), no price predictions, no financial advice, no links, max 1 hashtag, no emojis spam.\n')
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
             + (f'Coin in this story: {coin["name"]} ({coin["sym"]}) ${coin["price"]:,.6g}, {coin["h24"]:+.1f}% in 24h\n' if coin else '')
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
             'post': f'⚡ {item["title"]}' + (f'\n\n{coin["sym"]}: ${coin["price"]:,.6g} ({coin["h24"]:+.1f}% 24h)' if coin else '')}
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

REPLY_RULES = ('You are a real person running the crypto account "Chain Secrets", replying under an X post. Write the ONE best reply — '
               'the kind that gets the most likes under a big post.\n'
               'How it must sound: like a sharp human scrolling X, not a brand and not an AI. Casual, confident, short (usually 6-20 words, '
               'max 180 characters). Contractions, plain words, lowercase start is fine. One clear point: a dry joke, a sharp observation, '
               'or one real fact that adds context. React to what THIS post actually says.\n'
               'Never: em dashes, "Translation:", "This is huge", "Great post", "Let that sink in", "game changer", questions to farm '
               'engagement, hashtags, links, more than one emoji, financial advice, price predictions, or any number/fact you are not sure is true.\n'
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
    reply_from_text(post['text'] + (f'\n\n(Quoted post: {post["quote"]})' if post['quote'] else ''), post['author'], post, tgs, sid)


def reply_from_text(text, author, post, tgs, key):
    facts = f'Post by @{author}:\n{text[:2000]}'
    rp = parse_replies(gemini(REPLY_RULES + ('Use a different angle than the obvious one.\n' if key in tgs.get('replies', {}) else '')
                              + '\n' + facts))
    if not rp['reply']:
        unack(); tg('⚠️ The AI writer is busy, tap again in a minute.'); return
    coin = coin_from_text(text, rp['symbol']) if rp['chart'] and rp['symbol'] not in ('', 'NONE') else None
    img = move_card(coin)[0] if coin else None
    stats = f' · ❤️ {post["likes"]:,}' if post and post.get('likes') else ''
    stats += f' · {ago(post["ts"])}' if post and post.get('ts') else ''
    head = f'💬 <b>Reply for @{E(author)}</b>{stats}\n<i>{E(text[:160])}{"…" if len(text) > 160 else ""}</i>'
    tgs.setdefault('replies', {})[key] = {'t': time.time(), 'text': text[:2000], 'author': author}
    tgs['replies'] = dict(sorted(tgs['replies'].items(), key=lambda kv: -kv[1]['t'])[:30])
    unack()
    tg(reply_msg(rp, head, bool(img)), img, [('🔄 Another one', f'rr:{key}')])


def more_replies(key, tgs):
    r = tgs.get('replies', {}).get(key)
    if not r:
        tg('That one is too old. Send the link again.'); return
    chat_action('typing')
    reply_from_text(r['text'], r['author'], None, tgs, key)


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
    rp = parse_replies(gemini(REPLY_RULES + '\nThe post you reply to is a big account breaking this news:\n'
                              f'Headline: {lead["title"]}\nSources: {", ".join(sorted(srcs))}'
                              + (f'\nCoin: {coin["name"]} ({coin["sym"]}) {fmt_p(coin["price"])}, {coin["h24"]:+.1f}% 24h' if coin else '')))
    acc = who_posts(lead['title'])
    head = (f'🔥 <b>GOING VIRAL · REPLY WINDOW OPEN</b>\n<b>{E(lead["title"])}</b>\n{confirmed(srcs)} · {chance_txt(pr, sc)} · {age*60:.0f} min ago\n\n'
            f'👀 Watch for posts from: ' + ' · '.join(f'<a href="https://x.com/{a}">@{a}</a>' for a in acc)
            + '\nReply in the first 15 minutes with 👇')
    img = move_card(coin)[0] if coin and rp.get('chart') else None
    if rp['reply']:
        tg(reply_msg(rp, head, bool(img)), img, fb_buttons(mk))
    else:
        tg(head, img, fb_buttons(mk))


# ---------------- easy daily use: menu, briefings, feedback, tracking, weekly report ----------------
MENU = [['📰 Top stories', '📊 Movers'], ['💬 Reply to a post', '🏴‍☠️ Hacks'], ['📖 Story', '🧠 Brain']]
MENU_V = 2


def send_menu(text='👇 Your menu is ready at the bottom of the chat.'):
    kb = {'keyboard': [[{'text': b} for b in row] for row in MENU], 'resize_keyboard': True, 'is_persistent': True}
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
        if (k in pr and pr[k] < 0.35) or (k not in pr and sc < 45):          # only stories worth posting
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
    tg(m)


_SCHED = {}


def scheduler(tgs):
    """Runs inside the always-on listener: briefings 15:00 + 20:00 Beirut, nightly training, daily X checks, Sunday report."""
    import threading
    now = datetime.now(timezone.utc); day = now.strftime('%Y-%m-%d')
    jobs = []
    for hh, label in ((12, '☀️ <b>Afternoon briefing</b>'), (17, '🌆 <b>Evening briefing</b>')):
        if now.hour == hh and now.minute < 40 and tgs.get(f'brief{hh}') != day:
            tgs[f'brief{hh}'] = day; jobs.append(lambda l=label: brief(tgs, l))
    if now.hour == 0 and now.minute >= 30 and tgs.get('trained') != day:
        tgs['trained'] = day; jobs.append(lambda: (brain.label_due(time.time()), brain.train(), brain.save()))
    if now.hour == 9 and tgs.get('checked') != day:
        tgs['checked'] = day; jobs.append(check_mine)
    if now.weekday() == 6 and now.hour == 15 and now.minute < 40 and tgs.get('weekly') != day:
        tgs['weekly'] = day; jobs.append(weekly_report)
    for j in jobs:
        def run(j=j):
            try:
                j()
            except Exception as e:
                print('job fail', repr(e))
        threading.Thread(target=run, daemon=True).start()


HELP = ('🕵️ <b>Chain Radar</b>\n\n'
        '<b>Find stories</b>\n'
        '/top — hottest crypto stories right now → tap one for a full post\n'
        '/movers — biggest gainers & losers + why they moved\n'
        '/hacks — biggest hacks of the last 30 days\n'
        '/story — on this day in crypto (real prices & hacks)\n'
        '/brain — what the learning brain knows so far\n'
        '/story <i>topic</i> — research a story, e.g. <code>/story Do Kwon</code> → thread + Shorts script\n\n'
        '<b>Replies</b>\n'
        '• <b>Share any X post link</b> to me → 3 ready replies (fact, witty, chart + image)\n'
        '• Viral stories come with a 🔥 reply-window alert + ready replies\n\n'
        '<b>Make posts from anything</b>\n'
        '• <b>Forward</b> any news message from another channel to me → full post\n'
        '• <b>Paste a link</b> to any article → full post\n'
        '/chart BTC — pro candle chart (add 7d, 30d or 1y)\n\n'
        '<b>Alerts</b>\n'
        '/mute 3 — pause alerts for 3 hours · /unmute')
COMMANDS = [('top', 'Hottest stories now'), ('movers', 'Gainers & losers + why'), ('hacks', 'Biggest hacks (30 days)'),
            ('reply', 'Replies for an X post: /reply <link>'), ('story', 'On this day / research: /story Do Kwon'), ('chart', 'Candle chart: /chart BTC 7d'),
            ('brain', 'Learning brain status'), ('mute', 'Pause alerts: /mute 3'), ('unmute', 'Resume alerts'), ('help', 'How to use the bot')]


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
    tg(f'📈 <b>{E(coin["name"])} ({coin["sym"]})</b> · ${coin["price"]:,.6g} · {coin["h24"]:+.1f}% 24h', img,
       [(x.upper(), f'c:{coin["id"]}:{x}') for x in ('1d', '7d', '30d', '1y') if x != span])


def cmd_movers(tgs):
    m = [c for c in collect_market() if c['rank'] <= 100]
    if not m:
        tg('Market data unavailable, try again in a minute.'); return
    by = {c['sym']: c for c in m}
    upn = sum(1 for c in m if c['h24'] > 0)
    head = '📊 <b>Market pulse</b> · top 100 coins, 24h\n'
    for sym in ('BTC', 'ETH', 'SOL'):
        if sym in by:
            c = by[sym]; head += f'{"🟢" if c["h24"] >= 0 else "🔴"} {sym} ${c["price"]:,.0f} ({c["h24"]:+.1f}%)   '
    head += f'\n{"🟢" if upn >= 50 else "🔴"} {upn} up · {100 - upn if len(m) >= 100 else len(m) - upn} down\n'
    pf = lambda v: f'${v:,.0f}' if v >= 1000 else f'${v:,.2f}' if v >= 1 else f'${v:.4g}'
    row = lambda c: f'{c["sym"][:6]:<6}{pf(c["price"]):>11}{c["h24"]:>+8.1f}%{c["h1"]:>+7.1f}%'
    up = sorted(m, key=lambda c: -c['h24'])[:5]; dn = sorted(m, key=lambda c: c['h24'])[:5]
    fast = sorted(m, key=lambda c: -abs(c['h1']))[:3]
    msg = (head + '\n🚀 <b>Top gainers</b>\n<pre>' + f'{"COIN":<6}{"PRICE":>11}{"24H":>9}{"1H":>8}\n' + '\n'.join(map(row, up)) + '</pre>'
           + '\n🩸 <b>Top losers</b>\n<pre>' + '\n'.join(map(row, dn)) + '</pre>'
           + '\n⚡ <b>Moving right now (1h):</b> ' + ', '.join(f'{c["sym"]} {c["h1"]:+.1f}%' for c in fast)
           + '\n\n👇 Tap a coin → real chart + why it moved')
    tg(msg, None, [(f'{"🚀" if c["h24"] > 0 else "🩸"} {c["sym"]}', f'm:{c["id"]}') for c in up + dn])


def coin_move(cid, tgs):
    """Chart + likely reason (real headlines) for one mover, with a button to turn it into a post."""
    coin = coin_by_id(cid)
    if not coin:
        tg('Coin data unavailable right now.'); return
    rows, src, lab = candles(coin, '1d')
    mv = recent_move(rows, 86400)[0] if rows else coin['h24'] / 100
    verb = 'surges' if mv >= 0 else 'drops'
    title = f'{coin["name"]} {verb} {abs(mv) * 100:.1f}% in 24 hours'
    junk = r'predict|could be worth|millionaire|should you buy|buy now|top \d|which is|best crypto|to buy|forecast|\?$'
    heads = [h for h in gnews(f'"{coin["name"]}" crypto', 15) if re.search(re.escape(coin['name']) + '|' + re.escape(coin['sym']), h['title'], re.I)
             and not re.search(junk, h['title'], re.I) and time.time() - h['ts'] < 36 * 3600][:3]
    try:
        img = card.chart_card(title, coin, rows, lab, 'MOVER', src, focus=86400)[0] if rows else None
    except Exception as e:
        print('mover card fail', repr(e)); img = None
    msg = f'<b>{E(coin["name"])} ({coin["sym"]})</b> · ${coin["price"]:,.6g}\n24h {coin["h24"]:+.1f}% · 1h {coin["h1"]:+.1f}%\n\n'
    if heads:
        msg += '📰 <b>What the news says</b>\n' + '\n'.join(f'• <a href="{E(h["url"])}">{E(h["title"])}</a> <i>({E(h["src"])}, {ago(h["ts"])})</i>' for h in heads)
    else:
        msg += '📰 No coin-specific news in the last 2 days. The move looks market-driven.'
    k = hashlib.md5((cid + str(int(NOW / 600))).encode()).hexdigest()[:12]
    tgs['menu'][k] = {'t': NOW, 'title': title, 'url': heads[0]['url'] if heads else '', 'src': heads[0]['src'] if heads else 'CoinGecko',
                      'coin': cid, 'chart': True, 'tag': 'MARKET', 'focus': 86400, 'span': '1d',
                      'facts': 'Recent headlines about this coin:\n' + '\n'.join(f'- {h["title"]} ({h["src"]}, {ago(h["ts"])})' for h in heads)
                               + ('' if heads else 'No coin-specific news found; do not invent a reason, say the move looks market-driven.')}
    tg(msg, img, [('📝 Make full post', 'p:' + k), ('7D', f'c:{cid}:7d'), ('30D', f'c:{cid}:30d')])


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


def on_this_day(tgs):
    now = datetime.now(timezone.utc); md = (now.month, now.day)
    tg(f'⏳ Digging through crypto history for {now:%B %d}…')
    btc_now = (coin_by_id('bitcoin') or {}).get('price', 0)
    prices = []
    for yrs in (1, 2, 3, 5, 8, 10):
        try:
            d = now.replace(year=now.year - yrs)
        except ValueError:
            continue
        rows = coinbase('BTC', 86400, d.timestamp(), d.timestamp() + 86400)
        if rows:
            prices.append((d.year, rows[0][4]))
    r = get('https://api.llama.fi/hacks')
    hacks = []
    for h in (r.json() if r else []):
        dt = datetime.fromtimestamp(float(h.get('date', 0)), timezone.utc)
        if (dt.month, dt.day) == md and dt.year < now.year and float(h.get('amount') or 0) >= 1e6:
            hacks.append((dt.year, h))
    hacks.sort(key=lambda x: -float(x[1].get('amount') or 0))
    msg, btn = f'📜 <b>On this day in crypto · {now:%B %d}</b>\n', []
    if prices:
        msg += '\n💰 <b>Bitcoin on this date</b> <i>(and change to today)</i>\n<pre>' + '\n'.join(f'{y}  ${p:>10,.0f}   {(btc_now / p - 1) * 100:>+8,.0f}% since' for y, p in prices) \
               + (f'\nNow  ${btc_now:>10,.0f}' if btc_now else '') + '</pre>'
        y0, p0 = prices[-1]
        tgs['otd'] = {'year': y0, 'then': p0, 'now': btc_now, 'date': now.strftime('%b %d')}
        btn.append((f'📈 BTC {y0} vs today', 'o:btc'))
    if hacks:
        msg += '\n🏴‍☠️ <b>Hacks that happened on this date</b>\n'
        for n, (y, h) in enumerate(hacks[:4], 1):
            hk = hack_item(h, tgs)
            msg += f'<b>{n}.</b> {y} · {E(str(h.get("name")))} · ${float(h.get("amount") or 0)/1e6:,.1f}M · {E(hk["hack"]["method"])}\n'
            btn.append((f'📝 Hack {n}', 'p:' + hk['key']))
    if not prices and not hacks:
        msg += '\nNothing found for today. Try <code>/story Mt Gox</code> to research any story.'
    tg(msg + '\nTip: <code>/story Do Kwon</code> researches any story → thread + Shorts script.', None, btn)


def otd_card(tgs):
    o = tgs.get('otd')
    if not o:
        tg('Send /story first.'); return
    pct = (o['now'] / o['then'] - 1) * 100
    card.FOOTER_LEFT = ''
    img = card.versus_card(f'Bitcoin on this day: {o["year"]} vs today', (f'{o["date"]}, {o["year"]}', f'${o["then"]:,.0f}'),
                           ('Today', f'${o["now"]:,.0f}'), f'That is {pct:+,.0f}% in {datetime.now(timezone.utc).year - o["year"]} years.', 'MARKET', 'Coinbase daily candles',
                           (card.MUT, card.GRN if pct >= 0 else card.RED))
    post = f'Bitcoin on this day in {o["year"]}: ${o["then"]:,.0f}.\nToday: ${o["now"]:,.0f}.\n\nThat\'s {pct:+,.0f}%. Every chart hides a story.'
    tg(f'<b>Bitcoin: {o["year"]} vs today</b>', img)
    tg(f'📝 <b>POST</b> (tap to copy)\n<code>{E(post)}</code>')


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
        toast = 'On it…'
        if data.startswith('f:'):
            _, k, val = data.split(':', 2); toast = on_feedback(k, val, tgs)
        elif data.startswith('ps:'):
            toast = 'Logged ✅'
        try:
            requests.post(f'https://api.telegram.org/bot{TOKEN}/answerCallbackQuery', data={'callback_query_id': cb['id'], 'text': toast}, timeout=10)
        except Exception:
            pass
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
        elif data.startswith('rr:'):
            more_replies(data[3:], tgs)
        elif data.startswith('x:'):
            _, k, what = data.split(':', 2)
            send_extra(k, what)
        elif data == 'r:':
            live_top(tgs)
        elif data.startswith('m:'):
            coin_move(data[2:], tgs)
        elif data == 'o:btc':
            otd_card(tgs)
        elif data.startswith('c:'):
            _, cid, span = (data.split(':') + ['1d'])[:3]
            coin = coin_by_id(cid)
            if coin:
                send_coin_chart(coin, span if span in SPANS else '1d')
        return
    msg = msg or {}
    t = (msg.get('text') or msg.get('caption') or '').strip()
    if not t:
        return
    parts = t.split(); c = parts[0].lower().split('@')[0]; args = parts[1:]
    fwd = msg.get('forward_origin') or {}
    fwd_src = (fwd.get('chat') or {}).get('title') or (fwd.get('sender_user') or {}).get('first_name') or fwd.get('sender_user_name')
    MAP = {'📰 Top stories': '/top', '📊 Movers': '/movers', '🏴‍☠️ Hacks': '/hacks', '📖 Story': '/story', '🧠 Brain': '/brain'}
    if t in MAP:
        c, args = MAP[t], []
    if t == '💬 Reply to a post':
        tg('💬 Share or paste the X post link here and I\'ll write the best reply.'); return
    if c in ('/start', '/help', 'help'):
        tg(HELP); send_menu()
    elif c == '/brain':
        brain_status()
    elif c in ('/top', 'top', 'news'):
        if not send_cached_top():
            live_top(tgs)
    elif c == '/chart':
        cmd_chart(args)
    elif c == '/reply':
        if args and XLINK.search(args[0]):
            cmd_reply(args[0], tgs)
        elif args:
            ack('⏳ Writing replies…'); reply_from_text(' '.join(args), 'someone', None, tgs, hashlib.md5(t.encode()).hexdigest()[:10])
        else:
            tg('Send <code>/reply</code> + an X post link — or just paste/share the link to me.')
    elif XLINK.search(t) and not fwd:
        cmd_reply(XLINK.search(t).group(0), tgs)
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
        send_menu('🆕 <b>Chain Radar upgraded</b>\n\n'
                  '• Menu buttons are now at the bottom of the chat 👇\n'
                  '• Briefings at 15:00 and 20:00 (Beirut) with your 3 best stories\n'
                  '• Quiet 1:00–9:00: only huge news wakes you\n'
                  '• Tap 👍/👎 on alerts and ✅ Posted after posting — the brain learns from it\n'
                  '• Send me your own X post links and I\'ll track how they do'.replace('<b>', '').replace('</b>', ''))
    while time.time() < end - 5:
        global NOW
        NOW = time.time()
        try:
            scheduler(tgs)
        except Exception as e:
            print('scheduler fail', repr(e))
        if time.time() - last_scan > 600 and not (scan_t[0] and scan_t[0].is_alive()):   # news scan every 10 min
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
            save_tg(tgs); git_sync(force=True); last_save = time.time()
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
        t = {'menu': {}}
        cmd_movers(t); coin_move('solana', t); on_this_day(t); otd_card(t)
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
