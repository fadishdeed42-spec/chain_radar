"""16:9 renderer for the Trump-Iran long video (1920x1080).
usage: python3 render.py timeline.json still t1 t2 ...   -> stills/sheet
       python3 render.py timeline.json part A B          -> part_A.mp4 (frames A..B-1)
       python3 render.py timeline.json info"""
import json, math, os, sys, subprocess, datetime as D
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, '..', 'fonts')
W, H, FPS = 1920, 1080, int(os.environ.get('FPS', 30))
BG, BG2, CARD, LINE = (10, 11, 15), (17, 19, 26), (21, 23, 31), (44, 48, 60)
INK, MUTED, DIM = (238, 240, 245), (140, 147, 162), (78, 84, 98)
RED, GREEN, BTC, OIL, GOLD = (232, 65, 72), (52, 199, 89), (247, 147, 26), (64, 174, 255), (255, 196, 64)

_F = {}
def F(name, size, var=None):
    k = (name, size, var)
    if k not in _F:
        f = ImageFont.truetype(os.path.join(FD, name), int(size))
        if var: f.set_variation_by_name(var)
        _F[k] = f
    return _F[k]
BLACK, XB, BOLD, SEMI, MED = 'InterDisplay-Black.otf', 'InterDisplay-ExtraBold.otf', 'InterDisplay-Bold.otf', 'Inter-SemiBold.otf', 'Inter-Medium.otf'
MONO, MONOB = 'DejaVuSansMono.ttf', 'DejaVuSansMono-Bold.ttf'
LORA_I, LORA = 'Lora-Italic-Variable.ttf', 'Lora-Variable.ttf'

def clamp(x, a=0., b=1.): return max(a, min(b, x))
def out3(x): x = clamp(x); return 1 - (1 - x) ** 3
def outback(x):
    x = clamp(x); c = 1.7; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
def seg(t, a, b): return clamp((t - a) / max(1e-6, b - a))
def A(c, a): return (c[0], c[1], c[2], int(255 * clamp(a)))
def mix(c1, c2, x): return tuple(int(c1[i] + (c2[i] - c1[i]) * x) for i in range(3))

# ---------------------------------------------------------------- data
P = json.load(open(os.path.join(HERE, '..', '..', 'research', 'prices.json')))
BTCD = {k: v for k, v in P['btc'].items()}
WTID = P['wti']
def series(name, a, b):
    if name == 'btc':
        return [(k, BTCD[k]) for k in sorted(BTCD) if a <= k <= b]
    return [(k, WTID[k]) for k in sorted(WTID) if a <= k <= b]
def dnum(s): return D.date.fromisoformat(s).toordinal()
DAYS = ['03-01', '03-02', '03-07', '03-09', '03-11', '03-13', '03-16', '03-17', '03-20', '03-24', '03-26', '03-30', '03-31', '04-01', '04-06',
        '04-07', '04-16', '04-20', '05-23', '06-01', '06-05', '06-08', '06-09', '06-11', '08-06', '09-09', '09-12', '10-02', '10-09', '10-30', '11-01']
DAYS = ['2026-' + d for d in DAYS]
def prevday(s): return (D.date.fromisoformat(s) - D.timedelta(1)).isoformat()

# ---------------------------------------------------------------- text helpers
def tw(f, s): return f.getlength(s)
def fit(name, s, maxw, start, lo=20, var=None):
    z = start
    while z > lo and tw(F(name, z, var), s) > maxw: z -= 2
    return F(name, z, var)
def wrap(f, s, maxw):
    out, cur = [], ''
    for w in s.split():
        t = (cur + ' ' + w).strip()
        if tw(f, t) <= maxw or not cur: cur = t
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out
def text(d, xy, s, f, c, a=1., anchor='la', spacing=0):
    if a <= 0.004 or not s: return
    if spacing:
        x, y = xy
        tot = sum(tw(f, ch) for ch in s) + spacing * (len(s) - 1)
        if anchor[0] == 'm': x -= tot / 2
        elif anchor[0] == 'r': x -= tot
        for ch in s:
            d.text((x, y), ch, font=f, fill=A(c, a), anchor='l' + anchor[1]); x += tw(f, ch) + spacing
        return
    d.text(xy, s, font=f, fill=A(c, a), anchor=anchor)
def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([int(v) for v in box], radius=r, fill=fill, outline=outline, width=width)

def big(layer, cx, cy, s, f, c, scale=1., a=1., anchor='mm'):
    """text drawn once on its own image, scaled and pasted with alpha (pop / punch animations)"""
    if a <= 0.004: return
    bb = f.getbbox(s)
    w_, h_ = bb[2] - bb[0] + 20, bb[3] - bb[1] + 20
    im = Image.new('RGBA', (int(w_), int(h_)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10 - bb[0], 10 - bb[1]), s, font=f, fill=c + (255,))
    if abs(scale - 1) > .004:
        im = im.resize((max(1, int(w_ * scale)), max(1, int(h_ * scale))), Image.BICUBIC)
    if a < 1:
        al = im.getchannel('A').point(lambda v: int(v * a)); im.putalpha(al)
    x = cx - im.width / 2 if anchor[0] == 'm' else cx
    y = cy - im.height / 2
    layer.alpha_composite(im, (int(x), int(y)))

# ---------------------------------------------------------------- background
def make_bg():
    y = np.linspace(0, 1, H)[:, None, None]
    g = np.array(BG)[None, None, :] * (1 - y) + np.array(BG2)[None, None, :] * y
    g = np.repeat(g, W, axis=1)
    for x in range(0, W, 64): g[:, x, :] += 5
    for yy in range(0, H, 64): g[yy, :, :] += 5
    xx, yy = np.meshgrid(np.linspace(-1, 1, W), np.linspace(-1, 1, H))
    vig = 1 - .45 * np.clip((xx ** 2 * .7 + yy ** 2) - .15, 0, 1)
    g *= vig[:, :, None]
    return np.clip(g, 0, 255).astype(np.float32)
BGI = make_bg()
rng = np.random.default_rng(5)
GRAIN = [rng.normal(0, 3.2, (H // 2, W // 2, 1)).astype(np.float32) for _ in range(6)]
def glow(color, cx, cy, r, a):
    xx, yy = np.meshgrid(np.arange(W), np.arange(H))
    m = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r))) * a
    return m[:, :, None] * np.array(color)[None, None, :]
CH_GLOW = {}
def chapter_bg(c):
    if c not in CH_GLOW:
        col = [RED, RED, GOLD, OIL, RED, RED, BTC, MUTED, RED][c % 9]
        CH_GLOW[c] = np.clip(BGI + glow(col, W * .82, H * .12, 520, .07) + glow(col, W * .1, H * .95, 600, .04), 0, 255)
    return CH_GLOW[c]

# ---------------------------------------------------------------- timeline
TL = None; SC = []
def load(path):
    global TL, SC
    TL = json.load(open(path)); SC = TL['scenes']
    for k, s in enumerate(SC):
        s['k'] = k
        s['s0'] = 0.0 if k == 0 else s['a'] - .12
    for k, s in enumerate(SC):
        s['s1'] = SC[k + 1]['s0'] if k + 1 < len(SC) else TL['dur']
def norm(w): return ''.join(ch for ch in w.lower() if ch.isalnum() or ch == '-')
def wt(s, word, nth=0, default=None):
    if not word: return default
    n = norm(word); c = 0
    for w, a, b in s['words']:
        if norm(w) == n or (len(n) > 3 and norm(w).startswith(n)):
            if c == nth: return a
            c += 1
    return default
def hit_t(s, frac=.45):
    h = s['v'].get('hit')
    return wt(s, h, default=s['s0'] + frac * (s['s1'] - s['s0']))
CHNAMES = {0: 'THE NUMBER', 1: 'IN HIS OWN WORDS', 2: 'CH 1 · FOUR TO FIVE WEEKS', 3: 'CH 2 · DAYS AWAY', 4: 'CH 3 · "I THINK IT\'S OVER"',
           5: 'CH 4 · AFTER THE ELECTION', 6: 'CH 5 · DID THE MARKET BELIEVE HIM?', 7: 'HIS SIDE AND THE COUNT', 8: 'THE LESSON'}

# ---------------------------------------------------------------- scene painters (each draws on an RGBA layer)
def p_number(L, d, s, t):
    v = s['v']; t0 = s['s0']; x = out3(seg(t, t0, t0 + .35))
    small = v.get('small')
    sub = v.get('sub', '')
    col = INK
    if v['big'] in ('34',): col = RED
    if 'OIL' in sub or 'BRENT' in sub: col = OIL
    if v.get('somber'): col = (205, 205, 212)
    f = fit(BLACK, v['big'], 1560, 150 if small else 360)
    th = hit_t(s, .35); punch = 0
    if v.get('hit') and not v.get('somber'): punch = math.exp(-max(0, t - th) * 9) * (t >= th) * .07
    cy = 470 if sub else 520
    big(L, W / 2, cy, v['big'], f, col, scale=(.88 + .12 * x) * (1 + punch), a=x)
    if sub:
        fs = fit(SEMI, sub, 1500, 44)
        text(d, (W / 2, cy + f.size * .5 + 70), sub, fs, MUTED, out3(seg(t, t0 + .2, t0 + .55)), 'mm', spacing=3)
    if v.get('hit') and not v.get('somber'):
        u = out3(seg(t, th, th + .35)); ww = min(900, tw(f, v['big']) * .9) * u
        if u > 0: d.rectangle([W / 2 - ww / 2, cy + f.size * .5 + 22, W / 2 + ww / 2, cy + f.size * .5 + 30], fill=A(col, .9))

def p_stack(L, d, s, t):
    v = s['v']; ys = [330, 480, 630]
    for i, (it, h) in enumerate(zip(v['items'], v['hits'])):
        ta = wt(s, h, default=None)
        ta = (s['s0'] + .2) if i == 0 else (ta - .55 if ta else s['s0'] + .6 * i)
        if i == 0: ta = s['s0'] + .1
        x = out3(seg(t, ta, ta + .3))
        latest = all(t < (wt(s, v['hits'][j], default=99) - .55) for j in range(i + 1, 3)) if i < 2 else True
        f = F(XB, 104)
        text(d, (W / 2 - 40 * (1 - x), ys[i]), it, f, INK if latest else MUTED, x, 'mm')

def p_files(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; dur = t1 - t0
    for i, lab in enumerate(v['items']):
        ta = t0 + .1 + i * min(.45, dur * .15); x = out3(seg(t, ta, ta + .35))
        cx = 480 + 480 * i; cy = 470 + 40 * (1 - x)
        if x <= 0: continue
        rrect(d, (cx - 190, cy - 140, cx - 40, cy - 100), 10, fill=A((36, 40, 52), x))
        rrect(d, (cx - 190, cy - 115, cx + 190, cy + 135), 14, fill=A((28, 31, 41), x), outline=A(LINE, x), width=2)
        for k in range(3):
            d.rectangle([cx - 150, cy - 40 + k * 36, cx + 150 - k * 50, cy - 30 + k * 36], fill=A((52, 57, 71), x))
        text(d, (cx, cy + 95), lab, F(MONOB, 34), INK, x, 'mm', spacing=2)
    text(d, (W / 2 - (200 if v.get('stamp') else 0), 740), v['span'], F(MONO, 32), MUTED, out3(seg(t, t0 + .6, t0 + 1)), 'mm', spacing=2)
    if v.get('stamp'):
        ts = t0 + dur * .55; x = seg(t, ts, ts + .25)
        if x > 0:
            sc = 1.5 - .5 * out3(x)
            im = Image.new('RGBA', (560, 160), (0, 0, 0, 0)); dd = ImageDraw.Draw(im)
            rrect(dd, (8, 8, 552, 152), 16, outline=RED + (255,), width=8)
            dd.text((280, 82), v['stamp'], font=F(BLACK, 92), fill=RED + (255,), anchor='mm')
            im = im.rotate(-8, expand=True, resample=Image.BICUBIC)
            im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BICUBIC)
            al = im.getchannel('A').point(lambda q: int(q * min(1, x * 3) * .92)); im.putalpha(al)
            L.alpha_composite(im, (int(W / 2 + 470 - im.width / 2), int(700 - im.height / 2)))

def spark(d, box, pts, col, prog=1., width=5, fillbelow=True, a=1.):
    x0, y0, x1, y1 = box
    vals = [p for _, p in pts]; lo, hi = min(vals), max(vals); pad = (hi - lo) * .08
    lo -= pad; hi += pad
    n = len(pts); m = max(2, int(n * clamp(prog)))
    xy = [(x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * (vals[i] - lo) / (hi - lo)) for i in range(m)]
    if fillbelow and len(xy) > 1:
        d.polygon(xy + [(xy[-1][0], y1), (xy[0][0], y1)], fill=A(col, .12 * a))
    d.line(xy, fill=A(col, a), width=width, joint='curve')
    return xy

def p_duo(L, d, s, t):
    v = s['v']; t0 = s['s0']
    for i, (lab, col, ser) in enumerate([(v['a'], BTC, 'btc'), (v['b'], OIL, 'wti')]):
        x = out3(seg(t, t0 + .1 + .15 * i, t0 + .45 + .15 * i)); cx = 520 + 880 * i
        bx = (cx - 400, 300, cx + 400, 800)
        rrect(d, (bx[0], bx[1] + 30 * (1 - x), bx[2], bx[3] + 30 * (1 - x)), 22, fill=A(CARD, x), outline=A(col, .55 * x), width=3)
        text(d, (bx[0] + 40, bx[1] + 50 + 30 * (1 - x)), lab, F(XB, 56), col, x, 'lm')
        if v['reveal']:
            pts = [(k, c['close'] if isinstance(c, dict) else c) for k, c in series(ser, '2026-02-27', '2026-11-02')]
            pr = out3(seg(t, t0 + .3, s['s1'] - .4))
            spark(d, (bx[0] + 40, bx[1] + 120, bx[2] - 40, bx[3] - 70), pts, col, pr, 5, a=x)
            text(d, (bx[0] + 40, bx[3] - 35), 'FEB 27 → NOV 2' if ser == 'btc' else 'FEB 27 → OCT 27', F(MONO, 24), MUTED, x, 'lm')
        else:
            text(d, (cx, 590), '?', F(BLACK, 200), DIM, x, 'mm')

def p_chapter(L, d, s, t):
    v = s['v']; t0 = s['s0']; x = out3(seg(t, t0, t0 + .5))
    if v.get('num'): text(d, (W / 2, 380 + 20 * (1 - x)), v['num'], F(MONOB, 34), RED, x, 'mm', spacing=8)
    f = fit(BLACK, v['title'], 1600, 140)
    big(L, W / 2, 500 + 20 * (1 - x), v['title'], f, INK, 1, x)
    u = out3(seg(t, t0 + .25, t0 + .8)); ww = 520 * u
    d.rectangle([W / 2 - ww / 2, 590, W / 2 + ww / 2, 598], fill=A(RED, x))
    if v.get('sub'): text(d, (W / 2, 650), v['sub'].upper(), F(MONO, 32), MUTED, out3(seg(t, t0 + .4, t0 + .8)), 'mm', spacing=4)

def quoted_span(s):
    ws = s['words']; q0 = q1 = None
    for i, (w, a, b) in enumerate(ws):
        if '"' in w or '“' in w:
            if q0 is None: q0 = i
            q1 = i
    return q0, q1

def p_quote(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; fast = v.get('fast')
    x = out3(seg(t, t0, t0 + (.18 if fast else .32)))
    dy = 30 * (1 - x)
    rrect(d, (170, 200 + dy, 1750, 880 + dy), 26, fill=A(CARD, x * .96), outline=A(LINE, x), width=2)
    d.rectangle([170, 230 + dy, 178, 850 + dy], fill=A(RED, x))
    # header: date chip, number badge
    f = F(MONOB, 36); dw = tw(f, v['date'])
    rrect(d, (240, 250 + dy, 240 + dw + 44, 306 + dy), 10, fill=A(RED, x))
    text(d, (262, 278 + dy), v['date'], f, (255, 255, 255), x, 'lm')
    if v.get('n'):
        b = f'#{v["n"]} OF 34'; bw = tw(F(MONOB, 30), b)
        rrect(d, (1680 - bw - 40, 252 + dy, 1680, 304 + dy), 10, outline=A(RED, x), width=3)
        text(d, (1660, 278 + dy), b, F(MONOB, 30), RED, x, 'rm')
    elif v.get('paraphrase'):
        text(d, (1680, 278 + dy), 'PARAPHRASED · HIS EXPLANATION', F(MONO, 26), MUTED, x, 'rm')
    if not v.get('paraphrase'):
        text(d, (232, 300 + dy), '“', F(LORA_I, 260, 'Bold Italic'), A(RED, 1)[:3], x * .9, 'la')
    # the quote, word by word as it is spoken
    said = v['said']; size = 96 if len(said) < 40 else 84 if len(said) < 70 else 72
    while True:
        fq = F(LORA_I, size, 'Bold Italic'); lines = wrap(fq, said, 1300)
        if len(lines) <= 4 or size <= 52: break
        size -= 4
    lh = size * 1.22; top = 560 - lh * len(lines) / 2 + dy
    q0, q1 = quoted_span(s)
    nwords = len(said.split())
    if q0 is not None and q1 is not None and q1 >= q0:
        spoken = [w for w in s['words'][q0:q1 + 1]]
        done = sum(1 for w, a, b in spoken if a <= t + .05)
        frac = done / max(1, len(spoken))
        if t >= spoken[-1][1]: frac = 1
    else:
        frac = seg(t, t0 + .2, t0 + max(.6, (t1 - t0) * .7))
    if fast: frac = max(frac, seg(t, t0, t0 + .25) * 0)          # montage: still word by word
    shown = int(round(frac * nwords + (0 if frac < 1 else nwords)))
    k = 0
    for i, ln in enumerate(lines):
        xx = 330
        for w in ln.split():
            c = INK if k < shown else (60, 64, 78)
            text(d, (xx, top + i * lh), w, fq, c, x, 'la')
            xx += tw(fq, w + ' '); k += 1
    # footer
    text(d, (330, 790 + dy), '— ' + v['where'], F(SEMI, 36), INK, x, 'lm')
    text(d, (330, 836 + dy), 'SOURCE: ' + v['src'].upper(), F(MONO, 24), MUTED, x, 'lm')

def chart_box(): return (150, 250, 1700, 830)
def p_chart(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; ser = v['series']; col = BTC if ser == 'btc' else OIL
    rows = series(ser, v['a'], v['b'])
    x0, y0, x1, y1 = chart_box()
    a = out3(seg(t, t0, t0 + .3))
    prev = SC[s['k'] - 1]['v'] if s['k'] > 0 else {}
    cont = prev.get('kind') == 'chart' and prev.get('series') == ser and prev.get('a') == v['a'] and prev.get('b') <= v['b']
    if cont: a = 1
    if ser == 'btc':
        lo = min(r['low'] for _, r in rows); hi = max(r['high'] for _, r in rows)
    else:
        lo = min(r for _, r in rows); hi = max(r for _, r in rows)
    pad = (hi - lo) * .12; lo -= pad; hi += pad * 1.6
    da, db = dnum(v['a']), dnum(v['b'])
    X = lambda k: x0 + (x1 - x0) * (dnum(k) - da) / max(1, db - da)
    Y = lambda p: y1 - (y1 - y0) * (p - lo) / (hi - lo)
    # grid + labels
    for i in range(5):
        p = lo + (hi - lo) * (i + .5) / 5; yy = Y(p)
        d.line([(x0, yy), (x1, yy)], fill=A(LINE, .6 * a), width=1)
        lab = f'${p / 1000:,.1f}K' if ser == 'btc' else f'${p:,.0f}'
        text(d, (x1 + 18, yy), lab, F(MONO, 24), MUTED, a, 'lm')
    m0 = D.date.fromisoformat(v['a']).replace(day=1)
    while m0.isoformat() <= v['b']:
        if m0.isoformat() >= v['a']:
            xx = X(m0.isoformat()); d.line([(xx, y1), (xx, y1 + 10)], fill=A(MUTED, a), width=2)
            text(d, (xx, y1 + 30), m0.strftime('%b').upper(), F(MONO, 24), MUTED, a, 'mm')
        m0 = (m0 + D.timedelta(32)).replace(day=1)
    text(d, (x0, 205), v.get('title', ''), F(MONOB, 32), INK, a, 'lm', spacing=2)
    text(d, (x0, y1 + 70), 'Bitstamp BTC/USD daily candles (UTC)' if ser == 'btc' else 'WTI spot price, US Energy Information Administration via FRED',
         F(MONO, 22), DIM, a, 'lm')
    # reveal
    th = hit_t(s, .5)
    pend = clamp(th - .1, t0 + .8, t1 - .3) if v.get('hit') else t0 + max(.9, (t1 - t0) * .55)
    p0 = 0
    if cont:
        pr = [k for k, _ in rows if k <= prev['b']]; p0 = len(pr) / len(rows)
    pr_ = p0 + (1 - p0) * out3(seg(t, t0 + (0 if cont else .15), pend))
    n = max(1, int(round(len(rows) * pr_)))
    cw = max(2, (x1 - x0) / max(1, db - da) * .62)
    if ser == 'btc':
        for k, r in rows[:n]:
            xx = X(k); up = r['close'] >= r['open']; c = GREEN if up else RED
            d.line([(xx, Y(r['high'])), (xx, Y(r['low']))], fill=A(c, .95 * a), width=max(1, int(cw / 4)))
            ya, yb = sorted([Y(r['open']), Y(r['close'])])
            d.rectangle([xx - cw / 2, ya, xx + cw / 2, max(yb, ya + 2)], fill=A(c, a))
    else:
        xy = [(X(k), Y(p)) for k, p in rows[:n]]
        if len(xy) > 1:
            d.polygon(xy + [(xy[-1][0], y1), (xy[0][0], y1)], fill=A(col, .13 * a))
            d.line(xy, fill=A(col, a), width=6, joint='curve')
    # marker + tag
    mk = v.get('mark')
    if mk and n >= len(rows) * .999 or (mk and pr_ >= .999):
        mrow = [r for k, r in rows if k == mk]
        if mrow:
            r = mrow[0]; pv = r['close'] if ser == 'btc' else r
            mx, my = X(mk), Y(pv)
            tm = max(pend, t0 + .2); u = seg(t, tm, tm + .3)
            if u > 0:
                pulse = (t - tm) % 1.2 / 1.2
                d.ellipse([mx - 30 * pulse - 10, my - 30 * pulse - 10, mx + 30 * pulse + 10, my + 30 * pulse + 10], outline=A(col, (1 - pulse) * .8), width=3)
                d.ellipse([mx - 11, my - 11, mx + 11, my + 11], fill=A(INK, u), outline=A(col, u), width=4)
                tag = v.get('tag', '')
                tc = RED if tag.startswith('−') or tag.startswith('≈ −') else GREEN if tag.startswith('+') else col
                ft = F(BOLD, 48); twd = tw(ft, tag) + 44
                bx = clamp(mx - twd / 2, x0, x1 - twd); by = my - 120 if my > y0 + 160 else my + 50
                sc = outback(u)
                rrect(d, (bx, by, bx + twd, by + 72), 14, fill=A((14, 16, 22), .92 * u), outline=A(tc, u), width=3)
                text(d, (bx + twd / 2, by + 37), tag, ft, tc, u, 'mm')
                d.line([(mx, my - 14 if by < my else my + 14), (mx, by + 72 if by < my else by)], fill=A(tc, .7 * u), width=2)

def p_event(L, d, s, t):
    v = s['v']; t0 = s['s0']; x = out3(seg(t, t0, t0 + .4))
    if v.get('tag'): text(d, (W / 2, 330), v['tag'], F(MONOB, 34), RED, x, 'mm', spacing=6)
    f = fit(BLACK, v['date'], 1500, 150)
    u = out3(seg(t, t0 + .05, t0 + .5))
    big(L, W / 2, 450, v['date'], f, INK, .94 + .06 * u, u)
    d.rectangle([W / 2 - 300 * u, 540, W / 2 + 300 * u, 546], fill=A(RED, u))
    fh = F(BOLD, 66); lines = wrap(fh, v['head'], 1500)
    for i, ln in enumerate(lines):
        text(d, (W / 2, 620 + i * 80 + 20 * (1 - x)), ln, fh, (205, 210, 220), out3(seg(t, t0 + .25, t0 + .6)), 'mm')

# ---------------------------------------------------------------- Hormuz map (schematic, approximate coastlines)
IRAN = [(51.0, 29.5), (51.0, 27.9), (52.0, 27.45), (53.0, 26.95), (54.0, 26.62), (54.8, 26.55), (55.3, 26.75), (55.7, 27.02), (56.1, 27.16),
        (56.5, 27.08), (56.9, 26.8), (57.15, 26.2), (57.3, 25.85), (57.8, 25.72), (58.6, 25.58), (59.5, 25.4), (60.6, 25.3), (60.6, 29.5)]
ARAB = [(51.0, 22.0), (51.0, 24.2), (51.6, 24.1), (52.6, 24.15), (53.6, 24.15), (54.2, 24.35), (54.7, 24.85), (55.25, 25.3), (55.8, 25.65),
        (56.05, 26.05), (56.25, 26.32), (56.38, 26.38), (56.47, 26.15), (56.42, 25.8), (56.36, 25.35), (56.38, 24.95), (56.7, 24.45), (57.3, 23.9),
        (58.1, 23.62), (58.8, 23.45), (59.5, 22.7), (60.6, 22.0)]
QESHM = [(55.3, 26.62), (55.7, 26.72), (56.1, 26.88), (56.25, 26.95), (56.05, 26.98), (55.6, 26.86), (55.32, 26.72)]
VIEW = (50.8, 60.6, 23.0, 28.0)
def proj(lon, lat, z=1., cx=56.35, cy=26.5):
    lo0, lo1, la0, la1 = VIEW
    x = (lon - lo0) / (lo1 - lo0) * W; y = H - (lat - la0) / (la1 - la0) * H
    ccx, ccy = (cx - lo0) / (lo1 - lo0) * W, H - (cy - la0) / (la1 - la0) * H
    return (ccx + (x - ccx) * z, ccy + (y - ccy) * z)
def ship(d, x, y, col, a=1., s=1., ang=0.):
    pts = [(-22, -7), (16, -7), (26, 0), (16, 7), (-22, 7)]
    ca, sa = math.cos(ang), math.sin(ang)
    d.polygon([(x + (px * ca - py * sa) * s, y + (px * sa + py * ca) * s) for px, py in pts], fill=A(col, a))
LANE = [(51.9, 26.6), (53.5, 26.2), (55.0, 26.3), (55.9, 26.45), (56.35, 26.62), (56.75, 26.35), (57.2, 25.6), (58.3, 25.0), (59.6, 24.6)]
def lane_pt(u):
    u = u % 1; n = len(LANE) - 1; i = int(u * n); f = u * n - i
    a, b = LANE[i], LANE[min(n, i + 1)]
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, math.atan2(-(b[1] - a[1]), (b[0] - a[0]) * .9)
def p_map(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; x = out3(seg(t, t0, t0 + .4))
    z = 1 + .05 * seg(t, t0, t1)
    pj = lambda lo, la: proj(lo, la, z)
    d.rectangle([0, 0, W, H], fill=A((8, 18, 32), x))
    for poly, nm in ((IRAN, 'IRAN'), (ARAB, 'ARAB'), (QESHM, 'Q')):
        d.polygon([pj(*p) for p in poly], fill=A((34, 38, 48), x), outline=A((84, 92, 110), x))
    for lab, lo, la, sz in (('IRAN', 55.0, 27.55, 54), ('OMAN', 57.2, 23.62, 40), ('UAE', 54.0, 23.7, 40), ('PERSIAN GULF', 53.2, 25.5, 30),
                            ('GULF OF OMAN', 59.35, 25.0, 30), ('MUSANDAM (OMAN)', 56.1, 25.6, 22)):
        text(d, pj(lo, la), lab, F(MONOB if sz > 30 else MONO, sz), (120, 128, 145) if sz > 30 else (95, 104, 122), x, 'mm', spacing=4 if sz > 30 else 2)
    st = v['state']
    sx, sy = pj(56.3, 26.62)
    if st == 'closed':
        for k in range(6):
            ux, uy, ang = lane_pt(.05 + k * .045) if k < 3 else lane_pt(.72 + (k - 3) * .05)
            ship(d, *pj(ux, uy), (110, 116, 130), x, 1.2, ang)
        u = out3(seg(t, hit_t(s, .3), hit_t(s, .3) + .35)); pulse = .65 + .35 * math.sin(t * 6)
        a1, a2 = pj(56.22, 27.05), pj(56.42, 26.36)
        if u > 0:
            d.line([a1, (a1[0] + (a2[0] - a1[0]) * u, a1[1] + (a2[1] - a1[1]) * u)], fill=A(RED, pulse * x), width=12)
            text(d, (sx + 170, sy - 30), 'CLOSED', F(BLACK, 64), RED, u * x, 'lm')
    elif st == 'blockade':
        u = out3(seg(t, hit_t(s, .4) - .3, hit_t(s, .4) + .5))
        arc = [(57.05, 25.3), (57.5, 24.95), (58.0, 24.7), (58.5, 24.55), (59.0, 24.45)]
        for i, p in enumerate(arc):
            if u * len(arc) > i: ship(d, *pj(*p), (200, 215, 240), x, 1.5, .25)
        if u > 0: d.line([pj(*p) for p in arc], fill=A((200, 215, 240), .35 * u), width=2)
    elif st == 'open':
        for k in range(14):
            ux, uy, ang = lane_pt(k / 14 + (t - t0) * .045)
            ship(d, *pj(ux, uy), GREEN, x * .95, 1.1, ang)
        text(d, (sx + 170, sy - 30), 'OPEN', F(BLACK, 64), GREEN, out3(seg(t, hit_t(s, .5) - .2, hit_t(s, .5) + .2)) * x, 'lm')
    elif st == 'attack':
        th = hit_t(s, .3)
        for k, (lo, la) in enumerate(((56.0, 26.5), (56.55, 26.5), (56.9, 26.05))):
            px, py = pj(lo, la); ship(d, px, py, (160, 166, 180), x, 1.4, .3)
            tb = th + .25 * k; u = seg(t, tb, tb + .6)
            if 0 < u < 1:
                r = 20 + 90 * out3(u)
                d.ellipse([px - r, py - r, px + r, py + r], fill=A((255, 150, 40), (1 - u) * .7), outline=A((255, 220, 120), (1 - u)), width=4)
    # title box
    rrect(d, (60, 120, 760, 250), 16, fill=A((12, 14, 20), .85 * x), outline=A(LINE, x), width=2)
    text(d, (90, 168), v['label'], F(XB, 46), INK, x, 'lm')
    text(d, (90, 218), v['sub'], F(SEMI, 30), MUTED, x, 'lm')
    text(d, (W - 60, 92), 'Map: approximate coastlines', F(MONO, 20), (90, 98, 114), x, 'rm')

def p_ships(L, d, s, t):
    v = s['v']; t0 = s['s0']; x = out3(seg(t, t0, t0 + .4)); th = hit_t(s, .6); u = out3(seg(t, th - .2, th + .3))
    for side, val, lab, col, a_ in ((0, v['a'], 'SHIPS A DAY BEFORE THE WAR', INK, x), (1, v['b'], 'SHIPS ON AUGUST 26', RED, u)):
        cx = 520 + 880 * side
        big(L, cx, 380, str(val), F(BLACK, 230), col, 1, a_)
        text(d, (cx, 530), lab, F(SEMI, 34), MUTED, a_, 'mm', spacing=2)
        n = val / 10
        for i in range(13):
            if i >= math.ceil(n): break
            r, c = divmod(i, 5)
            ship(d, cx - 260 + c * 130, 640 + r * 70, col, a_ * (1 if i + 1 <= n else .45), 2.0)
    text(d, (W / 2, 900), 'each icon = 10 ships · source: AP', F(MONO, 22), DIM, x, 'mm')

def p_headline(L, d, s, t):
    v = s['v']; t0 = s['s0']; x = out3(seg(t, t0, t0 + .4)); dy = 40 * (1 - x)
    text(d, (W / 2, 205 + dy), 'HEADLINE', F(MONOB, 26), MUTED, x, 'mm', spacing=6)
    rrect(d, (260, 250 + dy, 1660, 830 + dy), 10, fill=A((242, 241, 236), x))
    text(d, (320, 320 + dy), v['src'], F('Lora-Variable.ttf', 48, 'Bold') if False else F(LORA, 50, 'Bold'), (20, 20, 24), x, 'lm')
    text(d, (1600, 320 + dy), v['date'], F(MONO, 26), (90, 90, 96), x, 'rm')
    d.line([(320, 370 + dy), (1600, 370 + dy)], fill=A((30, 30, 34), x), width=3)
    size = 70
    while True:
        fh = F(LORA, size, 'Bold'); lines = wrap(fh, v['head'], 1260)
        if len(lines) <= 4 or size < 44: break
        size -= 4
    for i, ln in enumerate(lines):
        text(d, (320, 420 + i * size * 1.22 + dy), ln, fh, (18, 18, 22), x, 'la')
    u = out3(seg(t, t0 + .6, t0 + 1.1))
    yy = 420 + len(lines) * size * 1.22 + 26 + dy
    d.rectangle([320, yy, 320 + 420 * u, yy + 8], fill=A(RED, x))

def p_post(L, d, s, t):
    v = s['v']; t0 = s['s0']; x = out3(seg(t, t0, t0 + .4)); dy = 40 * (1 - x)
    caps = v['text'].isupper()
    size = 104 if caps else 66
    while True:
        f = F(BLACK if caps else BOLD, size); lines = wrap(f, v['text'], 1060)
        if len(lines) <= 4 or size < 40: break
        size -= 4
    lh = size * 1.15; hgt = 200 + lh * len(lines) + 50
    top = H / 2 - hgt / 2 - 10 + dy
    rrect(d, (360, top, 1560, top + hgt), 26, fill=A(CARD, x), outline=A(LINE, x), width=2)
    d.ellipse([410, top + 50, 480, top + 120], fill=A((52, 57, 71), x))
    text(d, (505, top + 70), 'POST', F(MONOB, 30), INK, x, 'lm', spacing=3)
    text(d, (505, top + 106), v['where'], F(MED, 26), MUTED, x, 'lm')
    th = hit_t(s, .4) if v.get('hit') else t0 + .2
    for i, ln in enumerate(lines):
        u = out3(seg(t, min(th, t0 + .2) + i * .12, min(th, t0 + .2) + i * .12 + .35))
        text(d, (420, top + 180 + i * lh + 20 * (1 - u)), ln, f, INK, x * u, 'la')

def p_doc(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; x = out3(seg(t, t0, t0 + .4))
    im = Image.new('RGBA', (900, 760), (0, 0, 0, 0)); dd = ImageDraw.Draw(im)
    rrect(dd, (0, 0, 900, 760), 8, fill=(240, 238, 230, 255))
    dd.text((450, 90), v['title'], font=fit(LORA, v['title'], 780, 56, var='Bold'), fill=(20, 20, 24, 255), anchor='mm')
    dd.text((450, 150), v['sub'], font=F(MONO, 26), fill=(80, 80, 88, 255), anchor='mm')
    dd.line([(80, 195), (820, 195)], fill=(30, 30, 34, 255), width=3)
    for i, ln in enumerate(v['lines']):
        u = seg(t, t0 + .4 + i * .3, t0 + .7 + i * .3)
        if u > 0:
            dd.text((110, 270 + i * 90), '✓' if False else '•', font=F(BOLD, 44), fill=(20, 20, 24, int(255 * u)), anchor='lm')
            dd.text((160, 270 + i * 90), ln, font=F(SEMI, 40), fill=(20, 20, 24, int(255 * u)), anchor='lm')
    im = im.rotate(-1.5, expand=True, resample=Image.BICUBIC)
    al = im.getchannel('A').point(lambda q: int(q * x)); im.putalpha(al)
    L.alpha_composite(im, (int(W / 2 - im.width / 2), int(H / 2 + 20 - im.height / 2 + 30 * (1 - x))))
    th = hit_t(s, .6); u = seg(t, th, th + .25)
    if u > 0 and v.get('stamp'):
        sc = 1.5 - .5 * out3(u)
        st = Image.new('RGBA', (460, 150), (0, 0, 0, 0)); sd = ImageDraw.Draw(st)
        rrect(sd, (6, 6, 454, 144), 14, outline=RED + (255,), width=8)
        sd.text((230, 76), v['stamp'], font=F(BLACK, 90), fill=RED + (255,), anchor='mm')
        st = st.rotate(10, expand=True, resample=Image.BICUBIC).resize((int(490 * sc), int(200 * sc)), Image.BICUBIC)
        al = st.getchannel('A').point(lambda q: int(q * min(1, u * 3) * .9)); st.putalpha(al)
        L.alpha_composite(st, (int(W / 2 + 230 - st.width / 2), int(H / 2 + 230 - st.height / 2)))

def p_calendar(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; x = out3(seg(t, t0, t0 + .35))
    weeks, day = v['weeks'], v['day']
    prog = out3(seg(t, t0 + .2, t1 - .3))
    if weeks <= 6:
        cols, cw, chh = weeks + 1, 200, 200
        x0 = W / 2 - cols * cw / 2
        for i in range(cols):
            filled = prog * cols > i
            c = GREEN if i < 5 else RED
            rrect(d, (x0 + i * cw + 10, 380, x0 + (i + 1) * cw - 10, 380 + chh), 16, fill=A(c, (.85 if filled else .12) * x), outline=A(c, x), width=3)
            text(d, (x0 + i * cw + cw / 2, 380 + chh / 2), f'W{i + 1}' if i < 5 else '…', F(BLACK, 64), (12, 12, 16) if filled else c, x, 'mm')
    else:
        per = 13; rows = math.ceil(weeks / per); cw = 100; x0 = W / 2 - per * cw / 2
        for i in range(weeks):
            r, c = divmod(i, per); filled = prog * weeks > i; col = GREEN if i < 5 else RED
            rrect(d, (x0 + c * cw + 6, 300 + r * 104, x0 + (c + 1) * cw - 6, 300 + r * 104 + 90), 10, fill=A(col, (.85 if filled else .1) * x))
    text(d, (W / 2, 220), 'PROMISED: 4–5 WEEKS', F(MONOB, 36), GREEN, x, 'mm', spacing=4)
    cur = int(round(1 + (day - 1) * prog))
    big(L, W / 2, 800 if weeks > 6 else 720, f'DAY {cur}', F(BLACK, 130), RED, 1, x)
    if v.get('months'): text(d, (W / 2, 900 if weeks > 6 else 820), f'{v["months"]}+ MONTHS' if v['months'] >= 8 else f'{v["months"]} MONTHS', F(SEMI, 38), MUTED, x, 'mm', spacing=4)

def p_dots(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; x = out3(seg(t, t0, t0 + .35))
    rows = series('btc', '2026-02-27', '2026-11-02'); x0, y0, x1, y1 = chart_box()
    lo = min(r['close'] for _, r in rows) * .95; hi = max(r['close'] for _, r in rows) * 1.04
    da, db = dnum('2026-02-27'), dnum('2026-11-02')
    X = lambda k: x0 + (x1 - x0) * (dnum(k) - da) / (db - da); Y = lambda p: y1 - (y1 - y0) * (p - lo) / (hi - lo)
    prev = SC[s['k'] - 1]['v'] if s['k'] > 0 else {}
    full = prev.get('kind') == 'dots'
    pr = 1 if full else out3(seg(t, t0 + .1, t0 + 1.2))
    xy = [(X(k), Y(r['close'])) for k, r in rows][:max(2, int(len(rows) * pr))]
    d.line(xy, fill=A(BTC, .8 * x), width=4, joint='curve')
    for i in range(4):
        p = lo + (hi - lo) * (i + .5) / 4; text(d, (x1 + 18, Y(p)), f'${p / 1000:,.0f}K', F(MONO, 24), MUTED, x, 'lm')
    m0 = D.date(2026, 3, 1)
    while m0.isoformat() <= '2026-11-02':
        xx = X(m0.isoformat()); text(d, (xx, y1 + 30), m0.strftime('%b').upper(), F(MONO, 24), MUTED, x, 'mm')
        m0 = (m0 + D.timedelta(32)).replace(day=1)
    colored = v.get('show') == 'days'
    for i, k in enumerate(DAYS):
        ta = (t0 + .2 + i * .045) if colored else (t0 + 1.0 + i * (max(.6, (t1 - t0) - 1.6) / 31))
        if full and not colored: ta = t0
        u = seg(t, ta, ta + .2)
        if u <= 0: continue
        c = BTCD[k]['close']; up = c > BTCD[prevday(k)]['close']
        col = (GREEN if up else RED) if colored else INK
        px, py = X(k), Y(c); r = 9 * outback(u)
        d.ellipse([px - r, py - r, px + r, py + r], fill=A(col, u), outline=A((10, 10, 14), u), width=2)
    text(d, (x0, 205), 'BITCOIN · EVERY DAY HE SAID IT', F(MONOB, 32), INK, x, 'lm', spacing=2)
    lab = '31 DAYS  ·  ● UP   ● DOWN' if colored else '34 STATEMENTS'
    text(d, (x1, 205), lab, F(MONOB, 30), INK, x, 'rm')
    if colored:
        fw = F(MONOB, 30); base = x1 - tw(fw, lab)
        d.text((base + tw(fw, '31 DAYS  ·  '), 205), '●', font=fw, fill=A(GREEN, x), anchor='lm')
        d.text((base + tw(fw, '31 DAYS  ·  ● UP   '), 205), '●', font=fw, fill=A(RED, x), anchor='lm')
    text(d, (x0, y1 + 70), 'Bitstamp BTC/USD daily close · dot = a day he said the war would end soon', F(MONO, 22), DIM, x, 'lm')

def p_bars(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; x = out3(seg(t, t0, t0 + .35))
    text(d, (W / 2, 220), v['title'], F(MONOB, 36), INK, x, 'mm', spacing=3)
    mx = max(v['a'], v['b'], 1)
    for i, (val, lab, col) in enumerate(((v['a'], v['la'], GREEN), (v['b'], v['lb'], RED))):
        cx = 760 + 400 * i; g = out3(seg(t, t0 + .25 + i * .15, t0 + 1.1 + i * .15))
        hgt = 400 * val / mx * g
        rrect(d, (cx - 110, 820 - hgt, cx + 110, 820), 10, fill=A(col, x))
        big(L, cx, 820 - hgt - 70, str(int(round(val * g))), F(BLACK, 110), col, 1, x)
        text(d, (cx, 870), lab, F(MONOB, 32), MUTED, x, 'mm', spacing=3)

def p_coin(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; x = out3(seg(t, t0, t0 + .3))
    sp = seg(t, t0, t0 + 1.4); ang = (1 - (1 - sp) ** 2) * 8 * math.pi
    wdt = abs(math.cos(ang)) * 230 + 6; face = 'UP' if math.cos(ang) >= 0 else 'DOWN'
    cy = 450 - 160 * math.sin(math.pi * sp)
    col = GREEN if face == 'UP' else RED
    d.ellipse([W / 2 - wdt, cy - 230, W / 2 + wdt, cy + 230], fill=A((40, 43, 54), x), outline=A(col, x), width=10)
    face = '50/50' if sp >= 1 else face; col = INK if sp >= 1 else col
    if wdt > 120: text(d, (W / 2, cy), face, F(BLACK, 110), col, x * min(1, (wdt - 120) / 80), 'mm')
    text(d, (W / 2, 800), '16 UP · 15 DOWN', F(BLACK, 80), INK, out3(seg(t, t0 + 1.2, t0 + 1.6)), 'mm')
    text(d, (W / 2, 880), 'A COIN FLIP', F(MONOB, 34), MUTED, out3(seg(t, t0 + 1.3, t0 + 1.7)), 'mm', spacing=6)

def p_versus(L, d, s, t):
    v = s['v']; t0 = s['s0']; prevv = SC[s['k'] - 1]['v'] if s['k'] > 0 else {}
    xa = 1 if (prevv.get('kind') == 'versus') else out3(seg(t, t0, t0 + .35))
    xb = out3(seg(t, t0 + .2, t0 + .6)) if v['reveal'] else 0
    for i, (lab, val, col, a_) in enumerate(((v['a'], v['av'], INK, xa), (v['b'], v['bv'], RED, xb))):
        cx = 520 + 880 * i
        text(d, (cx, 400), lab, F(MONOB, 36), MUTED, a_, 'mm', spacing=5)
        f = fit(BLACK, val, 760, 120); big(L, cx, 540, val, f, col, .92 + .08 * a_, a_)
    d.line([(W / 2, 320), (W / 2, 760)], fill=A(LINE, xa), width=3)

EVENTS = [('2026-04-07', 'CEASEFIRE', 'seventh'), ('2026-04-13', 'BLOCKADE', 'blockade.'), ('2026-06-17', 'MEMORANDUM', 'memorandum.'),
          ('2026-07-08', 'COLLAPSE', 'collapse.'), ('2026-07-14', 'BLOCKADE AGAIN', 'blockade.')]
def p_events(L, d, s, t):
    v = s['v']; t0, t1 = s['s0'], s['s1']; x0, y0, x1, y1 = chart_box(); y0 += 60
    prevv = SC[s['k'] - 1]['v'] if s['k'] > 0 else {}
    cont = prevv.get('kind') == 'events'; x = 1 if cont else out3(seg(t, t0, t0 + .35))
    b0, w0 = BTCD['2026-02-27']['close'], WTID['2026-02-27']
    bs = [(k, (r['close'] / b0 - 1) * 100) for k, r in series('btc', '2026-02-27', '2026-11-02')]
    ws = [(k, (p / w0 - 1) * 100) for k, p in series('wti', '2026-02-27', '2026-10-27')]
    lo, hi = -20, 80
    da, db = dnum('2026-02-27'), dnum('2026-11-02')
    X = lambda k: x0 + (x1 - x0) * (dnum(k) - da) / (db - da); Y = lambda p: y1 - (y1 - y0) * (p - lo) / (hi - lo)
    for p in (-20, 0, 20, 40, 60, 80):
        d.line([(x0, Y(p)), (x1, Y(p))], fill=A(LINE if p else MUTED, (.5 if p else .8) * x), width=1 if p else 2)
        text(d, (x1 + 18, Y(p)), f'{p:+d}%' if p else '0%', F(MONO, 24), MUTED, x, 'lm')
    pr = 1 if cont else out3(seg(t, t0 + .15, t0 + 1.6))
    for rows, col in ((ws, OIL), (bs, BTC)):
        xy = [(X(k), Y(p)) for k, p in rows][:max(2, int(len(rows) * pr))]
        d.line(xy, fill=A(col, x), width=5, joint='curve')
    m0 = D.date(2026, 3, 1)
    while m0.isoformat() <= '2026-11-02':
        text(d, (X(m0.isoformat()), y1 + 30), m0.strftime('%b').upper(), F(MONO, 24), MUTED, x, 'mm'); m0 = (m0 + D.timedelta(32)).replace(day=1)
    text(d, (x0, 205), '% CHANGE SINCE THE DAY BEFORE THE WAR', F(MONOB, 32), INK, x, 'lm', spacing=2)
    text(d, (x1, 205), '— BITCOIN', F(MONOB, 30), BTC, x, 'rm')
    text(d, (x1 - 260, 205), '— US OIL', F(MONOB, 30), OIL, x, 'rm')
    if v.get('step'):
        seen = 0
        for k, (day, lab, word) in enumerate(EVENTS):
            nth = 1 if (lab == 'BLOCKADE AGAIN') else 0
            ta = wt(s, word, 0, None)
            if lab.startswith('BLOCKADE'): ta = wt(s, 'blockade.', 0, None)
            if ta is None: ta = t0 + .4 + k * .5
            if lab == 'BLOCKADE': ta -= .25
            u = out3(seg(t, ta - .15, ta + .25))
            if u <= 0: continue
            xx = X(day); top = y0 - 10 + [0, 1, 0, 1, 2][k] * 46
            for yy in range(int(top + 30), int(y1), 18): d.line([(xx, yy), (xx, yy + 9)], fill=A(INK, .55 * u), width=2)
            fl = F(MONOB, 24); lw = tw(fl, lab) + 20
            rrect(d, (xx - lw / 2, top, xx + lw / 2, top + 36), 8, fill=A((230, 232, 238), u))
            text(d, (xx, top + 18), lab, fl, (12, 12, 16), u, 'mm')
    text(d, (x0, y1 + 70), 'Bitstamp BTC/USD close; WTI spot (EIA via FRED, to Oct 27)', F(MONO, 22), DIM, x, 'lm')

COUNTS = [('AXIOS', '12', 'signals the war was about to end, by Mar 30'), ('CNN', '38', 'times he said a deal was close, by Jun 9'),
          ('CHAIN SECRETS', '34', 'dated statements, Mar 1 – Nov 1')]
def p_counts(L, d, s, t):
    v = s['v']; t0 = s['s0']; step = v['step']
    prevv = SC[s['k'] - 1]['v'] if s['k'] > 0 else {}
    text(d, (W / 2, 220), 'OTHER COUNTS, OTHER RULES', F(MONOB, 36), INK, 1 if prevv.get('kind') == 'counts' else out3(seg(t, t0, t0 + .35)), 'mm', spacing=4)
    for i, (who, n, what) in enumerate(COUNTS):
        if step < i + 1: break
        new = step == i + 1
        u = out3(seg(t, t0 + .1, t0 + .45)) if new else 1
        y = 340 + i * 150
        rrect(d, (260, y - 55 + 20 * (1 - u), 1660, y + 55 + 20 * (1 - u)), 16, fill=A(CARD, u), outline=A(RED if i == 2 else LINE, u), width=3 if i == 2 else 2)
        text(d, (310, y + 20 * (1 - u)), who, F(MONOB, 32), MUTED, u, 'lm', spacing=2)
        big(L, 720, y + 20 * (1 - u), n, F(BLACK, 86), RED if i == 2 else INK, 1, u)
        text(d, (800, y + 20 * (1 - u)), what, F(SEMI, 36), INK, u, 'lm')
    if step >= 3:
        u = out3(seg(t, t0 + .1, t0 + .45)) if step == 3 else 1
        text(d, (W / 2, 820), 'RULE: one dated, public statement per place, per day', F(MONO, 30), MUTED, u, 'mm')
    if step >= 4:
        u = out3(seg(t, t0 + .1, t0 + .45))
        text(d, (W / 2, 890), 'ALL 34 SOURCES ARE IN THE DESCRIPTION', F(MONOB, 34), GOLD, u, 'mm', spacing=3)

LESSONS = [("A PROMISE ISN'T A PRICE", '34 "soons" · bitcoin: 16 days up, 15 down'), ('WATCH WHAT YOU CAN MEASURE', 'Ships through Hormuz · the blockade · a signed paper'),
           ('"SOON" COMPARED TO WHAT?', '4–5 weeks → more than 8 months')]
def p_lesson(L, d, s, t):
    v = s['v']; t0 = s['s0']; step = v['step']
    prevv = SC[s['k'] - 1]['v'] if s['k'] > 0 else {}
    for i, (head, sub) in enumerate(LESSONS):
        if step < i + 1: break
        cur = step == i + 1
        new = cur and not (prevv.get('kind') == 'lesson' and prevv.get('step') == step)
        u = out3(seg(t, t0 + .05, t0 + .4)) if new else 1
        y = 300 + i * 200
        text(d, (330, y + 20 * (1 - u)), str(i + 1), F(BLACK, 130), RED if cur else DIM, u, 'mm')
        text(d, (430, y - 20 + 20 * (1 - u)), head, F(BLACK, 70), INK if cur else MUTED, u, 'lm')
        sa = u if cur and not new else (out3(seg(t, t0 + .5, t0 + .9)) if cur else .6)
        text(d, (432, y + 50 + 20 * (1 - u)), sub, F(SEMI, 36), MUTED if cur else DIM, sa if cur else .7, 'lm')

LOGO = None
def p_end(L, d, s, t):
    global LOGO
    v = s['v']; t0, t1 = s['s0'], s['s1']; x = out3(seg(t, t0, t0 + .5))
    if LOGO is None:
        im = Image.open(os.path.join(HERE, '..', '..', 'studio', 'chain_secrets_profile.png')).convert('RGBA').resize((260, 260), Image.LANCZOS)
        m = Image.new('L', (260, 260), 0); ImageDraw.Draw(m).ellipse([0, 0, 259, 259], fill=255); im.putalpha(m); LOGO = im
    lg = LOGO.copy(); al = lg.getchannel('A').point(lambda q: int(q * x)); lg.putalpha(al)
    L.alpha_composite(lg, (int(W / 2 - 130), int(250 + 20 * (1 - x))))
    ta = wt(s, 'Follow', default=t0); tb = wt(s, 'Every', default=t0 + 1.2)
    u1, u2 = out3(seg(t, ta, ta + .35)), out3(seg(t, tb, tb + .35))
    big(L, W / 2, 640, 'FOLLOW CHAIN SECRETS', F(BLACK, 100), INK, .92 + .08 * u1, u1)
    text(d, (W / 2, 750), 'EVERY CHART HIDES A STORY.', F(MONOB, 40), RED, u2, 'mm', spacing=6)

PAINT = {'number': p_number, 'stack': p_stack, 'files': p_files, 'duo': p_duo, 'chapter': p_chapter, 'quote': p_quote, 'chart': p_chart,
         'event': p_event, 'map': p_map, 'ships': p_ships, 'headline': p_headline, 'post': p_post, 'doc': p_doc, 'calendar': p_calendar,
         'dots': p_dots, 'bars': p_bars, 'coin': p_coin, 'versus': p_versus, 'events': p_events, 'counts': p_counts, 'lesson': p_lesson, 'end': p_end}

# ---------------------------------------------------------------- captions + HUD
def phrases():
    out = []
    for s in SC:
        cur = []
        for w in s['words']:
            cur.append(w)
            if len(cur) >= 7 or w[0][-1:] in '.?!' and len(cur) >= 3:
                out.append(cur); cur = []
        if cur:
            if out and len(cur) <= 2 and out[-1][-1][0][-1:] not in '.?!' and len(out[-1]) + len(cur) <= 9 and out[-1][0] in s['words']: out[-1] += cur
            else: out.append(cur)
    return out
PH = None
def captions(d, t):
    global PH
    if PH is None: PH = phrases()
    for i, ph in enumerate(PH):
        a = ph[0][1] - .08; b = (PH[i + 1][0][1] - .08) if i + 1 < len(PH) else ph[-1][2] + .5
        b = min(b, ph[-1][2] + .6)
        if a <= t < b:
            f = F(SEMI, 40); words = [w[0] for w in ph]
            tot = tw(f, ' '.join(words)); x = W / 2 - tot / 2; y = 1012
            rrect(d, (x - 24, y - 34, x + tot + 24, y + 34), 14, fill=(0, 0, 0, 150))
            for w, a_, b_ in ph:
                c = INK if a_ <= t + .02 else (150, 155, 168)
                d.text((x, y), w, font=f, fill=c + (255,), anchor='lm'); x += tw(f, w + ' ')
            return

def hud(d, s, t):
    text(d, (60, 52), 'CHAIN SECRETS', F(MONOB, 24), INK, .9, 'lm', spacing=2)
    d.rectangle([40, 44, 50, 60], fill=RED + (230,))
    text(d, (W - 60, 52), CHNAMES.get(s['c'], ''), F(MONO, 24), MUTED, .9, 'rm', spacing=1)
    # war-progress strip
    dur = TL['dur']; x = W * t / dur
    d.rectangle([0, H - 6, W, H], fill=(30, 33, 42, 255)); d.rectangle([0, H - 6, x, H], fill=RED + (255,))

# ---------------------------------------------------------------- frame
def scene_at(t):
    for s in SC:
        if s['s0'] <= t < s['s1']: return s
    return SC[-1]
def layer_for(s, t):
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    PAINT[s['v']['kind']](L, d, s, t)
    return L
NOFADE = {('chart', 'chart'), ('dots', 'dots'), ('versus', 'versus'), ('events', 'events'), ('counts', 'counts'), ('lesson', 'lesson'), ('duo', 'duo'), ('number', 'number')}
def frame(t):
    s = scene_at(t)
    base = chapter_bg(s['c']).copy()
    g = GRAIN[int(t * FPS) % len(GRAIN)]
    base[::2, ::2] += g; base[1::2, ::2] += g; base[::2, 1::2] += g; base[1::2, 1::2] += g
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert('RGBA')
    L = layer_for(s, t)
    k = s['k']; lt = t - s['s0']; fade = .22
    if k > 0 and lt < fade:
        p = SC[k - 1]; pair = (p['v']['kind'], s['v']['kind'])
        keep = pair in NOFADE and (pair[0] != 'chart' or (p['v'].get('series') == s['v'].get('series') and p['v'].get('a') == s['v'].get('a')))
        if pair[0] == 'number' and pair[1] == 'number' and p['v'].get('big') != s['v'].get('big'): keep = False
        if not keep:
            Lp = layer_for(p, t); u = lt / fade
            Lp.putalpha(Lp.getchannel('A').point(lambda q: int(q * (1 - u))))
            img.alpha_composite(Lp)
            L.putalpha(L.getchannel('A').point(lambda q: int(q * u)))
    img.alpha_composite(L)
    d = ImageDraw.Draw(img)
    hud(d, s, t); captions(d, t)
    return img.convert('RGB')

if __name__ == '__main__':
    load(sys.argv[1]); mode = sys.argv[2]
    nfr = int(TL['dur'] * FPS)
    if mode == 'info': print(json.dumps({'frames': nfr, 'dur': TL['dur'], 'scenes': len(SC)}))
    elif mode == 'still':
        ims = []
        for a in sys.argv[3:]:
            im = frame(float(a)); ims.append(im.resize((640, 360)))
        cols = 4; rows = math.ceil(len(ims) / cols)
        sheet = Image.new('RGB', (640 * cols, 360 * rows), (0, 0, 0))
        for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 640, (i // cols) * 360))
        sheet.save(os.environ.get('SHEET', os.path.join(os.path.dirname(sys.argv[1]), 'sheet.jpg')), quality=88)
    elif mode == 'part':
        a, b = int(sys.argv[3]), min(nfr, int(sys.argv[4]))
        out = os.path.join(os.path.dirname(sys.argv[1]), f'part_{a:06d}.mp4')
        p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                              '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
        for f_ in range(a, b):
            p.stdin.write(frame(f_ / FPS).tobytes())
        p.stdin.close(); p.wait()
