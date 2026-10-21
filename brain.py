"""Chain Radar learning brain.

1) Reads public crypto Telegram channels (t.me/s/<name>, no login) for news + VIEW COUNTS.
2) Logs every story with what we knew when we first saw it.
3) Six hours later labels it: did it really blow up (views far above the channel's normal, many outlets,
   or you posted / liked it)?
4) Every night trains a small logistic-regression model on those labels -> "viral chance %".
Everything is stored in state/brain.json and state/model.json (committed by the bot), so it keeps learning across runs.
"""
import json, math, os, re, threading, time, html, hashlib
from datetime import datetime, timezone

import requests

BRAIN_F, MODEL_F = 'state/brain.json', 'state/model.json'
LOCK = threading.RLock()
UA = {'User-Agent': 'Mozilla/5.0 (ChainRadar; +github.com/fadishdeed42-spec/chain_radar)'}

# Public crypto news channels (the same outlets post the same news on X). Channels that fail to load are skipped and logged.
CHANNELS = ['WatcherGuru', 'wublockchainenglish', 'cointelegraph', 'coindesk', 'lookonchainchannel', 'bitcoinmagazinetelegram',
            'TheBlockNews', 'decryptmedia', 'binance_announcements', 'PeckShieldAlert', 'tree_news_feed', 'crypto_headlines']

TOPICS = {'hack': r'hack|exploit|drain|stole|steal|breach|attack|phish', 'legal': r'arrest|charge|sentenc|lawsuit|sue[sd]?\b|court|indict|fraud|guilty',
          'etf': r'\betf', 'reg': r'\bsec\b|cftc|regulat|congress|senate|\bbill\b|\blaw\b|ban\b|white house|trump',
          'macro': r'\bfed\b|rate cut|rate hike|inflation|cpi|powell|tariff', 'whale': r'whale|transfer|moved|dormant|wallet',
          'price': r'surge|soar|rall|jump|crash|plung|dump|record|all-time high|\bath\b|liquidat|pump',
          'listing': r'list(s|ing)\b|delist', 'outage': r'outage|halt|paus|suspend|frozen|freez', 'company': r'blackrock|fidelity|strategy|tesla|coinbase|binance|tether|robinhood',
          'treasury': r'treasury|reserve|buys?\b|bought|purchase|holdings'}
_B = None


# ---------------------------------------------------------------- storage
def load():
    global _B
    with LOCK:
        if _B is None:
            try:
                _B = json.load(open(BRAIN_F))
            except Exception:
                _B = {}
            for k, v in (('stories', {}), ('chan', {}), ('xposts', []), ('mine', {}), ('posted', []), ('fb', {}), ('briefed', {})):
                _B.setdefault(k, v)
        return _B


def save():
    with LOCK:
        b = load(); now = time.time()
        b['stories'] = {k: s for k, s in b['stories'].items() if now - s['t0'] < 30 * 86400}
        b['xposts'] = b['xposts'][-600:]
        b['posted'] = [p for p in b['posted'] if now - p['t'] < 60 * 86400]
        b['mine'] = {k: m for k, m in b['mine'].items() if now - m['t'] < 60 * 86400}
        b['briefed'] = {k: t for k, t in b['briefed'].items() if now - t < 2 * 86400}
        os.makedirs('state', exist_ok=True)
        tmp = BRAIN_F + '.tmp'
        json.dump(b, open(tmp, 'w'), separators=(',', ':'))
        os.replace(tmp, BRAIN_F)


def words(t):
    return [w for w in re.findall(r'[a-z0-9$]+', t.lower()) if len(w) > 2][:40]


def topics(t):
    t = t.lower()
    return [k for k, rx in TOPICS.items() if re.search(rx, t)]


# ---------------------------------------------------------------- telegram channels
def _num(v):
    v = v.strip().upper().replace(',', '')
    m = re.match(r'([\d.]+)([KM]?)', v)
    if not m:
        return 0
    return int(float(m.group(1)) * {'': 1, 'K': 1e3, 'M': 1e6}[m.group(2)])


def _clean_title(text):
    t = re.split(r'\n', text.strip())[0]
    t = re.sub(r'^[^\w$#@"]+', '', t)                                          # leading emojis / flags
    t = re.sub(r'^(JUST IN|BREAKING|NEW|UPDATE|ALERT|LATEST)\s*[:\-–]\s*', '', t, flags=re.I)
    t = re.sub(r'[#$](?=[A-Za-z])', '', t)                                       # #Bitcoin -> Bitcoin, $BTC -> BTC
    return re.sub(r'\s+', ' ', t).strip()[:220]


def read_channel(name, timeout=8):
    """Recent posts of a public channel: [{text, title, views, ts, url, src}]. Empty list on failure."""
    try:
        r = requests.get(f'https://t.me/s/{name}', headers=UA, timeout=timeout)
        if not r.ok:
            return []
        out = []
        for chunk in r.text.split('data-post="')[1:]:
            post = chunk.split('"', 1)[0]
            m = re.search(r'(?s)class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', chunk)
            if not m:
                continue
            raw = re.sub(r'<br\s*/?>', '\n', m.group(1))
            text = html.unescape(re.sub(r'<[^>]+>', '', raw)).strip()
            v = re.search(r'tgme_widget_message_views">([^<]+)<', chunk)
            d = re.search(r'<time datetime="([^"]+)"', chunk)
            if not text or not d:
                continue
            ts = datetime.fromisoformat(d.group(1)).timestamp()
            title = _clean_title(text)
            if len(title) < 25:
                continue
            out.append({'text': text[:1500], 'title': title, 'views': _num(v.group(1)) if v else 0, 'ts': ts,
                        'url': f'https://t.me/{post}', 'src': name, 'tg': True})
        return out
    except Exception as e:
        print('channel fail', name, repr(e)[:80])
        return []


def collect_channels(now, fresh_h=6):
    """All channels in parallel. Also keeps each channel's 'normal' views (median of posts 3h+ old) for the labels."""
    from concurrent.futures import ThreadPoolExecutor
    b = load()
    with ThreadPoolExecutor(8) as ex:
        res = dict(zip(CHANNELS, ex.map(read_channel, CHANNELS)))
    ok, items = [], []
    for name, posts in res.items():
        if not posts:
            continue
        ok.append(name)
        old = sorted(p['views'] for p in posts if now - p['ts'] > 3 * 3600 and p['views'])
        with LOCK:
            c = b['chan'].setdefault(name, {})
            if old:
                c['median'] = old[len(old) // 2]
            c['seen'] = now
            for p in posts:                                                       # remember latest views per post (for labels)
                c.setdefault('views', {})[p['url']] = [p['views'], p['ts']]
            c['views'] = {u: v for u, v in c['views'].items() if now - v[1] < 2 * 86400}
        items += [p for p in posts if now - p['ts'] < fresh_h * 3600]
    print('telegram channels ok:', ok, '| failed:', [c for c in CHANNELS if c not in ok], '| posts', len(items))
    return items


def view_ratio(url, now, early=False):
    """How far above the channel's normal a post is. early=True normalizes by age so young posts are comparable."""
    name = url.split('/')[-2] if '/t.me/' in url else ''
    c = load()['chan'].get(name) or {}
    v = (c.get('views') or {}).get(url)
    med = c.get('median') or 0
    if not v or not med:
        return 0.0
    views, ts = v
    age_h = max(0.05, (now - ts) / 3600)
    if early or age_h < 3:
        return round(views / (med * min(1.0, age_h / 3) + 1), 2)                 # views so far vs. normal views at this age
    return round(views / (med + 1), 2)


# ---------------------------------------------------------------- story log + labels
def _jac(a, b):
    a, b = set(a), set(b)
    return len(a & b) / max(1, len(a | b))


def find_story(title, now, hours=24):
    w = words(title); best, bs = None, 0
    for k, s in load()['stories'].items():
        if now - s['t0'] > hours * 3600:
            continue
        j = _jac(w, s['w'])
        if j > bs:
            best, bs = k, j
    return best if bs >= 0.4 else None


def log_story(key, g, sc, lead, coin, srcs, now):
    """First sight: freeze the 'early' features. Later scans: update spread + views (used only for the label)."""
    with LOCK:
        b = load(); S = b['stories']
        k = key if key in S else (find_story(lead['title'], now) or key)
        tg_urls = [i['url'] for i in g['items'] if i.get('tg')]
        if k not in S:
            S[k] = {'t0': now, 'title': lead['title'][:200], 'w': words(' '.join(i['title'] for i in g['items'][:3])),
                    'tp': topics(lead['title']), 'coin': coin['sym'] if coin else '', 'h1': round(coin['h1'], 1) if coin else 0,
                    'src0': len(srcs), 'sc0': sc, 'hr': datetime.fromtimestamp(now, timezone.utc).hour,
                    'tg0': max([view_ratio(u, now, early=True) for u in tg_urls] or [0]),
                    'srcs': sorted(srcs)[:8], 'smax': len(srcs), 'vmax': 0, 'lab': None}
        s = S[k]
        s['smax'] = max(s['smax'], len(srcs))
        s['tgu'] = sorted(set(s.get('tgu', []) + tg_urls))[:6]
        s['vmax'] = max([s.get('vmax', 0)] + [view_ratio(u, now) for u in s['tgu']])
        return k


def label_due(now):
    """Label stories that are 6h+ old. Viral = far above normal views, or covered by many outlets, or you posted/liked it."""
    n = 0
    with LOCK:
        for k, s in load()['stories'].items():
            if s['lab'] is not None or now - s['t0'] < 6 * 3600:
                continue
            s['vmax'] = max([s.get('vmax', 0)] + [view_ratio(u, now) for u in s.get('tgu', [])])
            viral = s['vmax'] >= 2.0 or s['smax'] >= 6 or s.get('posted') or s.get('fb') == 1
            if s.get('fb') == -1 and not (s['vmax'] >= 3 or s['smax'] >= 8):
                viral = False                                                     # you said no: learn your taste
            s['lab'] = 1 if viral else 0; n += 1
    return n


def mark(title, field, value, now):
    with LOCK:
        k = find_story(title, now, hours=72)
        if k:
            load()['stories'][k][field] = value
        return k


# ---------------------------------------------------------------- model
D = 1 << 12


def _h(f):
    return int(hashlib.md5(f.encode()).hexdigest()[:8], 16) % D


def feats(s):
    """Only things known at first sight (no peeking at the future)."""
    f = ['b'] + ['w:' + w for w in set(s.get('w', []))] + ['t:' + t for t in s.get('tp', [])]
    f += ['coin:' + ('y' if s.get('coin') else 'n'), 'major:' + str(s.get('coin') in ('BTC', 'ETH'))]
    f += [f'src0:{min(s.get("src0", 1), 5)}', f'sc:{min(int(s.get("sc0", 0)) // 10, 10)}', f'hr:{s.get("hr", 0) // 3}']
    f += [f'tg:{min(int(s.get("tg0", 0) * 2), 8)}', f'mv:{min(int(abs(s.get("h1", 0)) // 2), 5)}']
    f += ['s:' + x for x in s.get('srcs', [])[:5]]
    if s.get('x'):
        f.append('x')
    return sorted({_h(x) for x in f})


def _xpost_examples():
    """Big X accounts' posts you shared: viral = likes far above that account's usual."""
    by = {}
    for p in load()['xposts']:
        by.setdefault(p['a'].lower(), []).append(p)
    ex = []
    for a, ps in by.items():
        if len(ps) < 5:
            continue
        med = sorted(p['likes'] for p in ps)[len(ps) // 2] or 1
        for p in ps:
            ex.append(({'w': words(p['text']), 'tp': topics(p['text']), 'x': 1}, 1 if p['likes'] >= 1.5 * med else 0, p['t']))
    return ex


def train(now=None):
    import numpy as np
    now = now or time.time()
    data = [(s, s['lab'], s['t0']) for s in load()['stories'].values() if s['lab'] is not None] + _xpost_examples()
    data.sort(key=lambda d: d[2])
    n, pos = len(data), sum(d[1] for d in data)
    info = {'n': n, 'pos': pos, 'trained': now, 'ready': False}
    if n < 60 or pos < 8 or n - pos < 8:
        json.dump(info, open(MODEL_F, 'w')); return info
    X = np.zeros((n, D), dtype=np.float32)
    for i, (s, _, _) in enumerate(data):
        X[i, feats(s)] = 1.0
    y = np.array([d[1] for d in data], dtype=np.float32)

    def fit(X, y, epochs=400, lr=0.5, l2=1e-3):
        w = np.zeros(X.shape[1], dtype=np.float32)
        cw = np.where(y == 1, 0.5 / max(y.mean(), 1e-3), 0.5 / max(1 - y.mean(), 1e-3))   # balanced classes
        for _ in range(epochs):
            p = 1 / (1 + np.exp(-(X @ w)))
            w -= lr * ((X.T @ ((p - y) * cw)) / len(y) + l2 * w)
        return w

    cut = int(n * 0.8)                                                            # honest check: train on older, test on newer
    auc = None
    if n - cut >= 15 and 0 < y[cut:].sum() < n - cut:
        w = fit(X[:cut], y[:cut]); sc = X[cut:] @ w; yt = y[cut:]
        order = np.argsort(sc); ranks = np.empty(len(sc)); ranks[order] = np.arange(1, len(sc) + 1)
        npos = yt.sum(); auc = float((ranks[yt == 1].sum() - npos * (npos + 1) / 2) / (npos * (len(yt) - npos)))
    w = fit(X, y)
    info.update({'auc': round(auc, 3) if auc is not None else None, 'w': {str(i): round(float(v), 4) for i, v in enumerate(w) if abs(v) > 1e-4},
                 'ready': n >= 150 and pos >= 15 and (auc or 0) >= 0.62})
    json.dump(info, open(MODEL_F, 'w'))
    print('brain trained', {k: v for k, v in info.items() if k != 'w'})
    return info


_M = {}


def model():
    try:
        st = os.stat(MODEL_F).st_mtime
        if _M.get('mt') != st:
            _M.clear(); _M.update(json.load(open(MODEL_F))); _M['mt'] = st
    except Exception:
        return {}
    return _M


def chance(story):
    """Viral chance 0-1, or None while the brain is still learning."""
    m = model()
    if not m.get('ready'):
        return None
    w = m['w']; z = sum(w.get(str(i), 0) for i in feats(story))
    return 1 / (1 + math.exp(-z))


def early_story(g, sc, lead, coin, srcs, now):
    """The same 'first sight' features for a story not logged yet (to score it right now)."""
    return {'w': words(' '.join(i['title'] for i in g['items'][:3])), 'tp': topics(lead['title']), 'coin': coin['sym'] if coin else '',
            'h1': coin['h1'] if coin else 0, 'src0': len(srcs), 'sc0': sc, 'hr': datetime.fromtimestamp(now, timezone.utc).hour,
            'tg0': max([view_ratio(i['url'], now, early=True) for i in g['items'] if i.get('tg')] or [0]), 'srcs': sorted(srcs)[:8]}


def status():
    b = load(); m = model()
    S = list(b['stories'].values()); lab = [s for s in S if s['lab'] is not None]
    days = (time.time() - min([s['t0'] for s in S] or [time.time()])) / 86400
    return {'stories': len(S), 'labeled': len(lab), 'viral': sum(s['lab'] for s in lab), 'days': days,
            'xposts': len(b['xposts']), 'mine': len(b['mine']), 'fb': sum(1 for s in S if s.get('fb')),
            'ready': bool(m.get('ready')), 'auc': m.get('auc'), 'trained': m.get('trained'),
            'chan': {k: v.get('median', 0) for k, v in b['chan'].items() if time.time() - v.get('seen', 0) < 86400}}
