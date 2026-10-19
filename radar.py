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
        s[k] = {i: t for i, t in s[k].items() if NOW - t < 72 * 3600}
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
    return groups


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
    return hashlib.md5(' '.join(sorted(list(g['w']))[:12]).encode()).hexdigest()[:12]


def remember(st, g, lead, coin, srcs):
    """Store a story so the owner can tap 'Make post' on it later."""
    k = key_of(g)
    st.setdefault('menu', {})[k] = {'title': lead['title'], 'url': lead['url'], 'src': lead['src'], 't': NOW,
                                    't0': min(i.get('ts', NOW) for i in g['items']),
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
    try:
        muted = json.load(open('state/tg.json')).get('mute_until', 0) > NOW
    except Exception:
        muted = False
    market, news, reddit, hacks = collect_market(), collect_news(), collect_reddit(), collect_hacks()
    print(f'market {len(market)} news {len(news)} reddit {len(reddit)} hacks {len(hacks)}')
    groups = cluster(news)
    scored = sorted([(score_group(g, market, reddit), g) for g in groups], key=lambda x: -x[0][0])
    sent = 0

    st['top'] = []
    for (sc, lead, coin, srcs, age), g in scored[:10]:
        st['top'].append([remember(st, g, lead, coin, srcs), sc, round(age * 60), len(srcs)])
    st['top_at'] = NOW
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
        if muted:
            continue
        when = datetime.fromtimestamp(float(h.get('date', NOW)), timezone.utc).strftime('%b %d')
        hk = hashlib.md5(k.encode()).hexdigest()[:12]
        hitem = {'t': NOW, 'title': f'{h.get("name")} hacked for ${amt/1e6:,.1f} million', 'url': '', 'src': 'DefiLlama', 'tag': 'HACK',
                 'hack': {'amount': card.big_money(f'${amt:,.0f}'), 'chain': str(h.get('chain') or (h.get('chains') or [''])[0] or ''),
                          'method': str(h.get('technique') or h.get('classification') or '')[:28], 'date': when},
                 'facts': f'Hack date: {when}. Chain: {h.get("chain") or h.get("chains")}. Method: {h.get("technique") or h.get("classification")}. Amount: ${amt:,.0f}. (DefiLlama hacks database.)'}
        st.setdefault('menu', {})[hk] = hitem
        img = card.alert_card(hitem['title'], hitem['hack']['amount'], [('Chain', hitem['hack']['chain']), ('Method', hitem['hack']['method']), ('Date', when)], 'HACKED', 'DefiLlama')
        tg(f'🚨 <b>HACK ALERT</b> · {E(str(h.get("name")))} · ${amt/1e6:,.1f}M\nVerify with a news source before posting.', img, [('📝 Make full post', 'p:' + hk)])
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
        if not muted:
            tg(m, coin_card(c, f'{c["name"]} {verb} {abs(c["h1"]):.1f}% in one hour', '1d', 'PRICE ALERT', card.GRN if c['h1'] > 0 else card.RED),
               [('📝 Make full post', 'p:' + remember(st, {'items': [{'title': f'{c["name"]} {verb} {abs(c["h1"]):.1f}% in one hour', 'url': '', 'src': 'CoinGecko', 'ts': NOW}], 'w': {c['id'], 'move', verb}}, {'title': f'{c["name"]} {verb} {abs(c["h1"]):.1f}% in one hour', 'url': (news_hit or {}).get('url', ''), 'src': (news_hit or {}).get('src', 'CoinGecko')}, c, {'CoinGecko'}))])
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
            if not muted:
                tg(story_msg(sc, lead, coin, srcs, g['items'], age, True), None, [('📝 Make full post + image', 'p:' + mk)])
            sent += 1
        elif sc >= WATCH:
            st['stories'][k] = NOW
            watch.append((sc, lead, srcs, remember(st, g, lead, coin, srcs)))
    if watch:
        msg = '📌 <b>Worth a look</b> (not urgent). Tap a number to get a full post:\n'
        for n, (sc, lead, srcs, mk) in enumerate(watch[:5], 1):
            msg += f'\n<b>{n}.</b> ({sc}/100, {len(srcs)} src) <a href="{E(lead["url"])}">{E(lead["title"])}</a>'
        if not muted:
            tg(msg, None, [(f'📝 {n}', 'p:' + w[3]) for n, w in enumerate(watch[:5], 1)])
    print('alerts sent', sent, 'watch', len(watch))
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
    sh('git add state/tg.json state/seen.json state/listen.log && git commit -qm "listen state [skip ci]"')
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
    for n, (k, sc, age, ns) in enumerate(top[:8], 1):
        it = st.get('menu', {}).get(k)
        if not it:
            continue
        msg += f'\n<b>{n}.</b> {"🔥" if sc >= ALERT else "•"} {E(it["title"])}  <i>({ns} src)</i>'
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
    msg, btn = header + '\nTap a number → I make the full post (title, image, post, thread).\n', []
    for n, ((sc, lead, coin, srcs, age), g) in enumerate(scored[:8], 1):
        k = remember(st, g, lead, coin, srcs)
        fire = '🔥' if sc >= ALERT else '•'
        msg += f'\n<b>{n}.</b> {fire} {E(lead["title"])}  <i>({len(srcs)} src, {age*60:.0f}m)</i>'
        btn.append((f'📝 {n}', 'p:' + k))
    tg(msg, None, btn)


def cg_search(sym):
    r = get('https://api.coingecko.com/api/v3/search', params={'query': sym})
    hits = [x for x in (r.json().get('coins', []) if r else []) if x['symbol'].upper() == sym.upper()]
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


SPANS = {'1d': (900, 96, 1, '24h · 15m candles'), '7d': (3600, 168, 7, '7d · 1h candles'),
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


def candles(coin, span='1d', event_ts=None):
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
    return (rows, 'CoinGecko', lab if event_ts else SPANS[span][3]) if len(rows) >= 8 else ([], '', '')


def coin_card(coin, title, span='1d', tag='BREAKING', col=None, note=None, event_ts=None, strict=False):
    """Candle card. strict=True (news posts): return None when the chart doesn't actually show a move worth showing."""
    rows, src, lab = candles(coin, span, event_ts)
    if not rows and not event_ts and span == '1d':
        rows, src, lab = candles(coin, '7d')
    if not rows:
        return None
    try:
        img, mv = card.chart_card(title, coin, rows, lab, tag, src, int(event_ts * 1000) if event_ts else None)
        if strict and abs(mv) < 0.02:
            print('chart skipped: move too small', round(mv * 100, 2))
            return None
        return img
    except Exception as e:
        print('card fail', repr(e))
        return None


def article_text(urls):
    for u in urls[:2]:
        r = get(u, timeout=8)
        if not r or 'html' not in r.headers.get('content-type', ''):
            continue
        t = re.sub(r'(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>', ' ', r.text)
        paras = [html.unescape(re.sub(r'<[^>]+>', '', p)).strip() for p in re.findall(r'(?is)<p[^>]*>(.*?)</p>', t)]
        paras = [p for p in paras if len(p) > 60]
        if paras:
            return ' '.join(paras)[:6000]
    return ''


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


def gemini(prompt):
    if not GEMINI:
        return ''
    for attempt in range(2):
        for model in gemini_models():
            try:
                r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                                  params={'key': GEMINI}, timeout=25,
                                  json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.7}})
                if r.ok:
                    parts = r.json()['candidates'][0]['content']['parts']
                    return ''.join(p.get('text', '') for p in parts).strip()
                print('gemini', model, r.status_code, r.text[:90].replace('\n', ' '))
            except Exception as e:
                print('gemini fail', model, e)
        time.sleep(6)
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
          'THREAD:\n1/ ...\n2/ ...\n3/ ...\n4/ ...\n'
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
                img = coin_card(coin, title, '1d', tag if tag != 'BREAKING' else 'MARKET', event_ts=item.get('t0'),
                                strict=not force and not item.get('chart'))
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


def deliver(p, img, url='', src='', buttons=None):
    tg(f'<b>{E(p["title"])}</b>' + ('\n🎨 Tap a design to switch the image:' if buttons else ''), img, buttons)
    tg(f'📝 <b>POST</b> (tap to copy)\n<code>{E(p["post"])}</code>' + (f'\n\n💬 <b>REPLY IDEA</b>\n<code>{E(p["reply"])}</code>' if p['reply'] else '')
       + (f'\n\n🔗 <a href="{E(url)}">{E(src or "source")}</a> · check facts before posting' if url else ''))
    if p['thread']:
        tg(f'🧵 <b>THREAD</b> (post 1 = image above)\n<code>{E(p["thread"])}</code>')
    if p.get('short'):
        tg(f'🎬 <b>SHORTS SCRIPT</b> (~40s)\n<code>{E(p["short"])}</code>')


def make_post(item):
    coin = coin_by_id(item['coin']) if item.get('coin') else None
    body = article_text(item.get('urls') or [item['url']]) if item.get('url') else ''
    facts = (f'Headline: {item["title"]}\nSources: {", ".join(item.get("srcs") or [item.get("src", "")])}\n'
             + (f'Coin in this story: {coin["name"]} ({coin["sym"]}) ${coin["price"]:,.6g}, {coin["h24"]:+.1f}% in 24h\n' if coin else '')
             + (item.get('facts', '') + '\n') + (f'Article text:\n{body}\n' if body else ''))
    extra = ('This is a true-story thread for a crypto story channel: tell it as a story with a twist, in time order.\n'
             'Also add a line: SHORT: <a 40-second voiceover script for a YouTube Short, max 110 words, hook in the first sentence>\n'
             if item.get('story') else '')
    p = parse_out(gemini(STYLE + FORMAT + extra + '\nFACTS:\n' + facts))
    if not p['title']:
        p = {'title': item['title'][:90], 'keyfact': '', 'reply': '', 'thread': '', 'tag': item.get('tag', 'BREAKING'), 'visual': '',
             'symbol': '', 'stat': '', 'timeline': '', 'versus': '', 'quote': '',
             'post': f'⚡ {item["title"]}' + (f'\n\n{coin["sym"]}: ${coin["price"]:,.6g} ({coin["h24"]:+.1f}% 24h)' if coin else '')}
        tg('⚠️ The AI writer is busy right now, so this one is a simple version. Tap the button again in a minute for the full post.')
    if not coin and p.get('symbol') not in ('', 'NONE') and re.search(r'\b' + re.escape(p['symbol']) + r'\b', facts, re.I):
        h = cg_search(p['symbol']); coin = coin_by_id(h['id']) if h else None
    chart_it = item.get('chart') or re.search(r'\b(pumps|dumps) \d', item['title']) or p.get('visual') == 'CHART'
    img = build_image(p, item, facts, coin if chart_it else None)
    k = hashlib.md5((item['title'] + str(NOW)).encode()).hexdigest()[:10]
    TGS.setdefault('designs', {})[k] = {'t': time.time(), 'p': p, 'item': {x: item.get(x) for x in ('title', 'src', 'tag', 'hack', 'url', 't0')},
                                         'facts': facts[:4000], 'coin': coin['id'] if coin else ''}
    TGS['designs'] = dict(sorted(TGS['designs'].items(), key=lambda kv: -kv[1]['t'])[:25])
    deliver(p, img, item.get('url', ''), item.get('src', ''), [(a, f'v:{k}:{b}') for a, b in options(p, item, coin)])


def switch_design(k, vis):
    d = TGS.get('designs', {}).get(k)
    if not d:
        tg('That post is too old to redesign. Make it again from /top.'); return
    coin = coin_by_id(d['coin']) if d.get('coin') and vis == 'CHART' else None
    img = build_image(d['p'], d['item'], d['facts'], coin, vis)
    tg(f'<b>{E(d["p"]["title"])}</b> · {vis.title()} design', img, [(a, f'v:{k}:{b}') for a, b in options(d['p'], d['item'], coin or d.get('coin'))])


HELP = ('🕵️ <b>Chain Radar</b>\n\n'
        '<b>Find stories</b>\n'
        '/top — hottest crypto stories right now → tap one for a full post\n'
        '/movers — biggest gainers & losers + why they moved\n'
        '/hacks — biggest hacks of the last 30 days\n'
        '/story — on this day in crypto (real prices & hacks)\n'
        '/story <i>topic</i> — research a story, e.g. <code>/story Do Kwon</code> → thread + Shorts script\n\n'
        '<b>Make posts from anything</b>\n'
        '• <b>Forward</b> any news message from another channel to me → full post\n'
        '• <b>Paste a link</b> to any article → full post\n'
        '/chart BTC — pro candle chart (add 7d, 30d or 1y)\n\n'
        '<b>Alerts</b>\n'
        '/mute 3 — pause alerts for 3 hours · /unmute')
COMMANDS = [('top', 'Hottest stories now'), ('movers', 'Gainers & losers + why'), ('hacks', 'Biggest hacks (30 days)'),
            ('story', 'On this day / research: /story Do Kwon'), ('chart', 'Candle chart: /chart BTC 7d'),
            ('mute', 'Pause alerts: /mute 3'), ('unmute', 'Resume alerts'), ('help', 'How to use the bot')]


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
    h = cg_search(sym)
    coin = coin_by_id(h['id']) if h else None
    if not coin:
        tg(f'Couldn\'t find a coin called {E(sym)}.'); return
    send_coin_chart(coin, span)


def send_coin_chart(coin, span='1d'):
    lab = SPANS[span][3].split(' · ')[0]
    img = coin_card(coin, f'{coin["name"]}: the last {lab}' if span != '1d' else f'{coin["name"]} in the last 24 hours', span,
                    {'1d': '24H CHART', '7d': '7D CHART', '30d': '30D CHART', '1y': '1Y CHART'}[span])
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
    verb = 'surges' if coin['h24'] >= 0 else 'drops'
    title = f'{coin["name"]} {verb} {abs(coin["h24"]):.1f}% in 24 hours'
    heads = [h for h in gnews(f'"{coin["name"]}" crypto', 10) if re.search(re.escape(coin['name']) + '|' + re.escape(coin['sym']), h['title'], re.I)][:3]
    img = coin_card(coin, title, '1d', 'MOVER')
    msg = f'<b>{E(coin["name"])} ({coin["sym"]})</b> · ${coin["price"]:,.6g}\n24h {coin["h24"]:+.1f}% · 1h {coin["h1"]:+.1f}%\n\n'
    if heads:
        msg += '📰 <b>What the news says</b>\n' + '\n'.join(f'• <a href="{E(h["url"])}">{E(h["title"])}</a> <i>({E(h["src"])}, {ago(h["ts"])})</i>' for h in heads)
    else:
        msg += '📰 No coin-specific news in the last 2 days. The move looks market-driven.'
    k = hashlib.md5((cid + str(int(NOW / 600))).encode()).hexdigest()[:12]
    tgs['menu'][k] = {'t': NOW, 'title': title, 'url': heads[0]['url'] if heads else '', 'src': heads[0]['src'] if heads else 'CoinGecko',
                      'coin': cid, 'chart': True, 'tag': 'MARKET',
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
        msg += '\n💰 <b>Bitcoin on this date</b>\n<pre>' + '\n'.join(f'{y}  ${p:>10,.0f}   {(btc_now / p - 1) * 100:>+8,.0f}% since' for y, p in prices) \
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
                           ('Today', f'${o["now"]:,.0f}'), f'That is {pct:+,.0f}% in {datetime.now(timezone.utc).year - o["year"]} years.', 'MARKET', 'Coinbase daily candles')
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
        try:
            requests.post(f'https://api.telegram.org/bot{TOKEN}/answerCallbackQuery', data={'callback_query_id': cb['id'], 'text': 'On it…'}, timeout=10)
        except Exception:
            pass
        data = cb.get('data') or ''
        if data.startswith('p:'):
            item = menu_item(data[2:], tgs)
            if item:
                tg(f'⏳ Making your post: <b>{E(item["title"])}</b>')
                make_post(item)
            else:
                tg('That story expired. Send /top for the current list.')
        elif data.startswith('v:'):
            _, k, vis = data.split(':', 2)
            switch_design(k, vis)
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
    if c in ('/start', '/help', 'help'):
        tg(HELP)
    elif c in ('/top', 'top', 'news'):
        if not send_cached_top():
            live_top(tgs)
    elif c == '/chart':
        cmd_chart(args)
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
            tg('⏳ Reading the article and making your post…')
            pg = get(url); ttl = re.search(r'(?is)<title[^>]*>(.*?)</title>', pg.text) if pg else None
            ttl = html.unescape(ttl.group(1)).split(' | ')[0].split(' - ')[0].strip() if ttl else url
            make_post({'title': ttl, 'url': url, 'src': re.sub(r'^https?://(www\.)?([^/]+).*', r'\2', url), 'urls': [url]})
        else:                                            # forwarded or pasted news text
            tg('⏳ Turning this news into a post…')
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
    while time.time() < end - 5:
        global NOW
        NOW = time.time()
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
