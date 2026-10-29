"""Automatic Chain Secrets Short: renders any storyboard with the house engine (cs.py + engine.py + kit20.py).

python auto.py JOBDIR stills 1.0 4.5 ...    -> JOBDIR/sheet.png (preview frames)
python auto.py JOBDIR part A B              -> JOBDIR/part_A.mp4 (frames A..B)
python auto.py JOBDIR sfx                   -> JOBDIR/sfx.wav

JOBDIR holds storyboard.json, timing.json and (if the story has a chart) data.json with real daily candles.
Every scene is one of the template types below; its punch lands on the scene's "hit" word (B['s<i>'])."""
import os, sys, json, math, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
JOB = sys.argv[1]
import cs
cs.load(os.path.join(JOB, 'timing.json'))
from cs import *
from kit20 import *

SB = json.load(open(os.path.join(JOB, 'storyboard.json')))
TONE = SB['tone']
PACK = {  # tone style packs
    'funny':   dict(acc=GOLD, alt=UP, bad=DN, shake=1.0, whip=1.0, person=(150, 158, 176), impacts=('hook', 'turn', 'twist', 'payoff', 'end')),
    'serious': dict(acc=(110, 150, 230), alt=(150, 170, 200), bad=DN, shake=.35, whip=.45, person=(120, 128, 146), impacts=('twist', 'payoff')),
    'mystery': dict(acc=PURPLE, alt=(190, 160, 255), bad=DN, shake=.55, whip=.6, person=(110, 104, 140), impacts=('hook', 'twist', 'payoff')),
    'hype':    dict(acc=UP, alt=GOLD, bad=DN, shake=1.2, whip=1.0, person=(150, 158, 176), impacts=('hook', 'turn', 'twist', 'payoff', 'end')),
}[TONE]
ACC, ALT, BAD = PACK['acc'], PACK['alt'], PACK['bad']
cs.SHAKE, cs.WHIP = PACK['shake'], PACK['whip']
cs.TAGLINE = 'every chart hides a story' if SB.get('chart') else ''
# ---------------------------------------------------------------- Studio settings
import story as _story
ST = _story.settings(SB)
if ST['captions'] == 'off': cs.CAPS = []
elif ST['captions'] == 'large': cs.CAP_SIZE = 72
if ST['motion'] == 'calm': cs.SHAKE, cs.WHIP = .3, .4
elif ST['motion'] == 'strong': cs.SHAKE, cs.WHIP = 1.45, 1.15
SFX_K = {'off': 0, 'soft': .55, 'normal': 1.0, 'punchy': 1.35}.get(ST['sfx'], 1.0)
STYLE = ST.get('style', 'mixed')
LOOK = ST.get('look', 'none')
import looklib
PACE = {'calm': 2.6, 'normal': 1.8, 'fast': 1.25}.get(ST.get('pace', 'normal'), 1.8)   # max seconds without a new on-screen moment
MOVE = {'calm': .6, 'auto': 1.0, 'strong': 1.35}.get(ST['motion'], 1.0)
EP = SB.get('ep', '')
SCN = SB['scenes']

# ---------------------------------------------------------------- real chart data (optional)
D = ch = None
if SB.get('chart') and os.path.exists(os.path.join(JOB, 'data.json')):
    D = json.load(open(os.path.join(JOB, 'data.json')))
    ch = Chart(D, box=(30, 420, 862, 1240))
    import datetime as _dt

    def didx(ymd):
        ts = _dt.datetime.strptime(ymd, '%Y-%m-%d').replace(tzinfo=_dt.UTC).timestamp()
        return min(range(len(D['t'])), key=lambda i: abs(D['t'][i] - ts))
    CHART_SCENES = [i for i, s in enumerate(SCN) if s['visual']['type'] == 'chart']
    MARK = {i: didx(SCN[i]['visual'].get('date') or SB['chart']['end']) for i in CHART_SCENES}


# ---------------------------------------------------------------- real footage + photos (media.py fetched them)
MEDIA = {}
if STYLE not in ('graphics', '3d') and os.path.exists(os.path.join(JOB, 'media.json')):
    MEDIA = {int(k): v for k, v in json.load(open(os.path.join(JOB, 'media.json'))).items() if os.path.exists(os.path.join(JOB, v['file']))}
_yy = np.linspace(0, 1, RH, dtype=np.float32)[:, None, None]
GRADE = (.50 - .22 * np.clip((.22 - _yy) / .22, 0, 1) - .36 * np.clip((_yy - .6) / .4, 0, 1)).astype(np.float32)   # darker top + bottom
_BGF = np.array(BG, np.float32)
_cache = {}


def cover(img, w, h):
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    nw, nh = int(iw * s + .5), int(ih * s + .5)
    im = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    x0, y0 = (nw - w) // 2, max(0, int((nh - h) * .3))
    return im[y0:y0 + h, x0:x0 + w]


CUT = 2.4                                                              # seconds per clip: a scene cuts between its clips


def _clip(i, k, f):
    key = ('src', i) if k == 0 else ('src', i, k)
    if key not in _cache:
        cap = cv2.VideoCapture(os.path.join(JOB, f))
        _cache[key] = {'cap': cap, 'fps': cap.get(cv2.CAP_PROP_FPS) or 30, 'n': max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))), 'pos': -1, 'img': None}
    return _cache[key]


def media_frame(i, t):
    m = MEDIA[i]; key = ('src', i)
    if m['kind'] != 'video' and key not in _cache:
        im = cv2.imread(os.path.join(JOB, m['file']), cv2.IMREAD_COLOR)
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) if im is not None else None
        if im is not None and not m.get('real'): im *= min(1.0, 85.0 / max(1.0, float(im.mean())))
        _cache[key] = {'img': im}
    tl = max(0.0, t - P(i))
    if m['kind'] == 'video':
        files = [m['file']] + list(m.get('more') or [])
        k = int(tl // CUT) % len(files) if len(files) > 1 else 0
        c = _clip(i, k, files[k])
        tl = tl - (tl // CUT) * CUT if len(files) > 1 else tl           # each clip restarts at its own start
        tl += (int(max(0.0, t - P(i)) // (CUT * len(files)))) * CUT      # ...and continues on its next visit
        idx = int(tl * c['fps']) % max(1, c['n'] - 2)
        if idx != c['pos']:
            if idx != c['pos'] + 1: c['cap'].set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, fr = c['cap'].read()
            if ok:
                im = cover(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(np.float32), RW, RH)
                if 'gain' not in c: c['gain'] = min(1.0, 85.0 / max(1.0, float(im.mean())))   # bright clips are toned down
                c['img'] = im * c['gain']
            c['pos'] = idx
        return c['img']
    c = _cache[key]
    if c['img'] is None: return None
    if ('cov', i) not in _cache: _cache[('cov', i)] = cover(c['img'], int(RW * 1.15), int(RH * 1.15))
    im = _cache[('cov', i)]
    p = smooth(seg(t, P(i), PARA[i][1]))                                  # Ken Burns: slow push + pan
    z = 1 / 1.15 * (1 + .1 * p); d = 1 if i % 2 else -1
    M = np.float32([[z, 0, (RW - im.shape[1] * z) / 2 + d * 30 * K * (p - .5)], [0, z, (RH - im.shape[0] * z) / 2]])
    return cv2.warpAffine(im, M, (RW, RH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def backdrop(cv, t, i):
    if i not in MEDIA: return
    a = 1.0 if i == len(SCN) - 1 else fade(t, i)
    if i == 0 and len(SCN) > 1: a = 1 - seg(t, P(1) - .2, P(1))
    if a <= .01: return
    real_person = MEDIA[i].get('real') and SCN[i]['visual']['type'] == 'person'
    im = media_frame(i, t)
    if im is None: return
    if real_person:                                                       # the portrait is drawn sharp; behind it a soft blur of it
        if ('blur', i) not in _cache: _cache[('blur', i)] = cv2.GaussianBlur(cv2.resize(im, (RW // 8, RH // 8)), (0, 0), 6)
        im = cv2.resize(_cache[('blur', i)], (RW, RH))
    if LOOK != 'none' and not real_person: im = looklib.apply(LOOK, im, t)
    g = im * (GRADE * (.75 if real_person else 1)) + _BGF * (1 - GRADE) * .35
    cv.a += (g - cv.a) * a


def portrait(cv, i, cx, cy, r, alpha):
    """real photo in a round frame (face = upper part of the photo)"""
    c = _cache.get(('src', i)) or (media_frame(i, P(i)) is not None and _cache.get(('src', i)))
    if not c or c.get('img') is None or r < 4 or alpha <= 0: return False
    sz = int(2 * r * K)
    if ('por', i, sz) not in _cache:
        src = c['img']; h, w = src.shape[:2]; sd = min(h, w)
        y0 = int(max(0, min(h - sd, h * .08))) if h > w else 0
        sq = src[y0:y0 + sd, (w - sd) // 2:(w - sd) // 2 + sd]
        yy, xx = np.mgrid[0:sz, 0:sz]
        mk = np.clip(sz / 2 - np.sqrt((xx - sz / 2 + .5) ** 2 + (yy - sz / 2 + .5) ** 2), 0, 1).astype(np.float32)
        _cache[('por', i, sz)] = (cv2.resize(sq, (sz, sz), interpolation=cv2.INTER_AREA), mk)
        if len(_cache) > 60: [_cache.pop(k) for k in [k for k in _cache if k[0] == 'por'][:20]]
    im, mk = _cache[('por', i, sz)]
    x0, y0 = int(cx * K - sz / 2), int(cy * K - sz / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(RW, x0 + sz), min(RH, y0 + sz)
    roi = cv.a[ya:yb, xa:xb]; mm = mk[ya - y0:yb - y0, xa - x0:xb - x0, None] * alpha
    roi += (im[ya - y0:yb - y0, xa - x0:xb - x0] - roi) * mm
    cv.ring(cx, cy, r + 4, ACC, 10, alpha)
    return True


def hit(i):
    h = B.get(f's{i}', P(i) + .4)
    if SCN[i]['role'] == 'end':                                          # the payoff must be on screen well before the end card
        h = min(h, P(i) + max(.5, .55 * (h - P(i))))
    return h


def fit(text, kind, size, maxw):
    while size > 30 and text_size(text, kind, size)[0] > maxw: size -= 4
    return size


def wrap(text, n):
    """split into lines of about n characters"""
    out, cur = [], ''
    for w in str(text).split():
        if cur and len(cur) + 1 + len(w) > n: out.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    if cur: out.append(cur)
    return out


# ---------------------------------------------------------------- icon library
def flame(cv, x, y, s, a, t):
    for k, (col, sc) in enumerate((((246, 90, 40), 1.0), ((255, 170, 40), .7), ((255, 230, 120), .4))):
        w = 110 * s * sc; h = 230 * s * sc; f = 1 + .06 * math.sin(t * 9 + k)
        cv.poly([(x - w, y + 60 * s), (x - w * .8, y - h * .3 * f), (x - w * .2, y - h * .6), (x, y - h * f), (x + w * .3, y - h * .55),
                 (x + w * .8, y - h * .35 * f), (x + w, y + 60 * s), (x, y + 100 * s * sc)], col, a)


def skull(cv, x, y, s, a):
    cv.circle(x, y - 30 * s, 120 * s, (226, 230, 238), a); cv.rect(x - 70 * s, y + 40 * s, x + 70 * s, y + 120 * s, (226, 230, 238), a, r=20 * s)
    for dx in (-48, 48): cv.circle(x + dx * s, y - 30 * s, 34 * s, BG, a)
    cv.poly([(x, y + 10 * s), (x - 16 * s, y + 40 * s), (x + 16 * s, y + 40 * s)], BG, a)
    for k in range(4): cv.rect(x - 52 * s + k * 30 * s, y + 80 * s, x - 34 * s + k * 30 * s, y + 118 * s, BG, a)


def bank(cv, x, y, s, a):
    col = (150, 158, 176)
    cv.poly([(x - 260 * s, y - 120 * s), (x, y - 240 * s), (x + 260 * s, y - 120 * s)], col, a)
    for k in range(5): cv.rect(x - 210 * s + k * 100 * s, y - 100 * s, x - 170 * s + k * 100 * s, y + 140 * s, col, a, r=6 * s)
    cv.rect(x - 260 * s, y + 140 * s, x + 260 * s, y + 180 * s, col, a, r=6 * s)


def phone(cv, x, y, s, a, t):
    cv.rect(x - 120 * s, y - 220 * s, x + 120 * s, y + 220 * s, (60, 66, 82), a, r=34 * s)
    cv.rect(x - 104 * s, y - 196 * s, x + 104 * s, y + 196 * s, (24, 30, 44), a, r=22 * s)
    for k in range(3):
        cv.rect(x - 80 * s, y - 140 * s + k * 90 * s, x + 80 * s, y - 80 * s + k * 90 * s, ACC if k == 0 else (60, 70, 92), a, r=12 * s)


def token(cv, x, y, s, a, label='?'):
    r = 140 * s
    cv.glow(x, y, r * 1.5, ACC, .22 * a); cv.circle(x, y, r, tuple(int(c * .7) for c in ACC), a); cv.circle(x, y, r * .8, ACC, a)
    cv.text(x, y, label, 'black', max(6, int(r * .9)), WHITE, a, anchor='cm')


def cash(cv, x, y, s, a):
    for k in range(5):
        yy = y + 60 * s - k * 34 * s
        cv.rect(x - 200 * s, yy - 60 * s, x + 200 * s, yy + 60 * s, (40, 120, 70), a, r=12 * s)
        cv.rect(x - 186 * s, yy - 48 * s, x + 186 * s, yy + 48 * s, (70, 170, 100), a, r=8 * s)
        cv.circle(x, yy, 34 * s, (40, 120, 70), a)
        cv.text(x, yy, '$', 'black', max(6, int(52 * s)), (200, 240, 210), a, anchor='cm')
    cv.rect(x - 30 * s, y - 120 * s, x + 30 * s, y + 130 * s, (220, 200, 140), a * .9)


ICON_NAMES = set(_story.ICONS)


def icon(cv, name, x, y, s, a, t=0.0):
    if a <= 0 or s <= .02: return
    y += 9 * s * math.sin(t * 2.1 + x * .01)                             # idle float: icons are never frozen
    if name == 'bitcoin': coin(cv, x, y, 150 * s, a, rot=.3 * math.sin(t * 2))
    elif name == 'ethereum': eth_logo(cv, x, y, 160 * s, a)
    elif name == 'dogecoin': doge(cv, x, y, 150 * s, a)
    elif name == 'lock': padlock(cv, x, y, 1.5 * s, a, ACC)
    elif name == 'plane': plane(cv, x, y, .9 * s, a)
    elif name == 'laptop': laptop(cv, x, y + 100 * s, 1.1 * s, a, glow=.8)
    elif name == 'house': house(cv, x, y + 40 * s, .9 * s, a)
    elif name == 'safe': safe(cv, x, y, 1.0 * s, a)
    elif name == 'car': car(cv, x, y, 1.2 * s, a)
    elif name == 'crown': crown(cv, x, y, 1.0 * s, a)
    elif name == 'robot': robot(cv, x, y, 1.0 * s, a, t=t)
    elif name == 'gavel': gavel(cv, x - 120 * s, y + 60 * s, 1.1 * s, -.6, a)
    elif name == 'officer': officer(cv, x, y - 40 * s, 1.3 * s, a)
    elif name == 'person': person(cv, x, y - 40 * s, 1.3 * s, PACK['person'], a)
    elif name == 'calendar': calendar(cv, x, y, 1.0 * s, a, '', '')
    elif name == 'phone': phone(cv, x, y, s, a, t)
    elif name == 'bank': bank(cv, x, y, s, a)
    elif name == 'fire': flame(cv, x, y, s, a, t)
    elif name == 'skull': skull(cv, x, y, s, a)
    elif name == 'token': token(cv, x, y, s, a, '?')
    elif name == 'cash': cash(cv, x, y, s, a)
    else:
        cv.glow(x, y, 160 * s, ACC, .2 * a); cv.text(x, y, '?', 'black', max(6, int(260 * s)), ACC, a, anchor='cm')


import random as _r
_r.seed(7)
DUST = [(_r.uniform(0, W), _r.uniform(0, H), _r.uniform(2, 6), _r.uniform(8, 30), _r.uniform(0, 6.28)) for _ in range(38)]


def ambient(cv, t):
    """slow drifting particles in the tone colour: the frame is never static"""
    for x, y, r, sp, ph in DUST:
        yy = (y - t * sp) % H; xx = x + 18 * math.sin(t * .4 + ph)
        cv.circle(xx, yy, r, ACC, .10 + .06 * math.sin(t * 1.3 + ph))


KICK = {'setup': {'funny': 'MEET THE STAR', 'serious': 'THE BACKSTORY', 'mystery': 'THE SETUP', 'hype': 'HERE\'S THE DEAL'},
        'turn': {'funny': 'AND THEN…', 'serious': 'THEN', 'mystery': 'BUT THEN…', 'hype': 'THEN BOOM'},
        'twist': {'funny': 'PLOT TWIST', 'serious': 'THE TRUTH', 'mystery': 'THE TWIST', 'hype': 'PLOT TWIST'},
        'payoff': {'funny': 'THE RESULT', 'serious': 'THE COST', 'mystery': 'THE ANSWER', 'hype': 'THE RESULT'},
        'end': {'funny': 'TODAY', 'serious': 'TODAY', 'mystery': 'TODAY', 'hype': 'TODAY'}}


def kicker(cv, t, i, a, y=420):
    role = SCN[i]['role']
    if role == 'hook' or role not in KICK: return
    q = back(seg(t, P(i), P(i) + .35))
    k = KICK[role][TONE]
    pill(cv, W / 2, y, k, ACC, a * clamp(q), size=38, fg=BG if ACC in (GOLD, UP) else WHITE, s=max(.01, q))


# ---------------------------------------------------------------- scene templates
def sc_title(cv, t, i, v, a):
    h = hit(i)
    if SCN[i]['role'] == 'hook':                                         # hook: the big words land in the first half second
        h = min(h, P(i) + .45)
    else:
        kicker(cv, t, i, a)
    ic = v.get('icon')
    if ic: icon(cv, ic, W / 2, 620, back(seg(t, P(i), P(i) + .4)) * .9, a * (1 - .4 * seg(t, h, h + .3)), t)
    lines = wrap(str(v.get('text', '')).upper(), 12)[:3] or ['']
    y0 = 1000 if ic else 860
    if t < h - .05:                                                      # before the hit: the words wait faintly, never an empty frame
        g = back(seg(t, P(i) + .1, P(i) + .5)) * .28
        for k, ln in enumerate(lines):
            size = fit(ln, 'black', 150, 980)
            cv.text(W / 2, y0 + k * size * 1.02, ln, 'black', size, MUTED, a * g, anchor='cm', scale=.92)
    if t >= h - .05:
        for k, ln in enumerate(lines):
            size = fit(ln, 'black', 150, 980)
            slam(cv, t, h - .05 + k * .12, ln, y0 + k * size * 1.02, size, ACC if k == len(lines) - 1 else TXT, a)
        if v.get('sub'):
            cv.text(W / 2, y0 + len(lines) * 150 + 10, str(v['sub']).upper(), 'xbold', fit(str(v['sub']).upper(), 'xbold', 46, 960), MUTED,
                    a * seg(t, h + .3, h + .6), anchor='cm', track=4)


def fmt_num(v, pre, suf, big=None):
    big = abs(v) if big is None else big                                  # 4,300,000,000 -> 4.3B (scale fixed by the final value)
    if big >= 1e9: return f'{pre}{v / 1e9:,.1f}B{suf}'.replace('.0B', 'B')
    if big >= 1e7: return f'{pre}{v / 1e6:,.1f}M{suf}'.replace('.0M', 'M')
    if abs(v) >= 100: s = f'{v:,.0f}'
    elif abs(v) >= 10: s = f'{v:,.1f}'.rstrip('0').rstrip('.')
    else: s = f'{v:,.2f}'.rstrip('0').rstrip('.')
    return f'{pre}{s}{suf}'


def sc_counter(cv, t, i, v, a):
    h = hit(i)
    try: val = float(str(v.get('value', 0)).replace(',', '').replace('$', ''))
    except ValueError: val = 0
    pre, suf = str(v.get('prefix', '')), str(v.get('suffix', ''))
    ic = v.get('icon') or ('bitcoin' if 'BTC' in suf.upper() else 'cash' if '$' in pre else None)
    if SCN[i]['role'] != 'hook': kicker(cv, t, i, a)
    if ic: icon(cv, ic, W / 2, 680, back(seg(t, P(i), P(i) + .4)) * .85, a, t)
    p = out3(seg(t, h - .25, h + .75))
    s = fmt_num(val * p, pre, suf, abs(val))
    size = fit(fmt_num(val, pre, suf), 'black', 130, 900)
    yc = 1050 if ic else 880
    q = back(seg(t, P(i) + .1, P(i) + .5))                                # the counter waits at 0, then runs on the hit word
    counter(cv, s, yc, size, ALT if val >= 0 else BAD, a * clamp(q) * (.55 + .45 * clamp(p * 4)), glow=p > 0)
    if v.get('label'):
        cv.text(W / 2, yc + size * .85, str(v['label']).upper(), 'black', fit(str(v['label']).upper(), 'black', 46, 960), MUTED,
                a * seg(t, P(i) + .3, P(i) + .6), anchor='cm', track=10)


def sc_stamp(cv, t, i, v, a):
    h = hit(i)
    q = back(seg(t, P(i), P(i) + .45))
    icon(cv, v.get('icon') or 'question', W / 2, 760, q, a, t)
    if v.get('label'):
        cv.text(W / 2, 1080, str(v['label']).upper(), 'black', fit(str(v['label']).upper(), 'black', 52, 960), TXT, a * clamp(q), anchor='cm', track=4)
    if t >= h - .1:
        w = str(v.get('word', 'BUSTED')).upper()
        stamp(cv, t, h - .1, w, W / 2, 1300, fit(w, 'black', 92, 760), BAD if v.get('bad', True) else ALT, a)


def sc_person(cv, t, i, v, a):
    h = hit(i)
    q = back(seg(t, P(i), P(i) + .4))
    prop = v.get('prop', 'none')
    if i in MEDIA and MEDIA[i].get('real') and portrait(cv, i, W / 2, 720, 300 * max(.01, q), a * clamp(q)): pass
    elif prop == 'officer': officer(cv, W / 2, 760, 1.4 * q, a)
    else: person(cv, W / 2, 760, 1.4 * q, PACK['person'], a)
    name = str(v.get('name', '')).upper()
    cv.text(W / 2, 1110, name, 'black', fit(name, 'black', 60, 980), TXT, a * clamp(q), anchor='cm', track=4)
    if t >= h - .2:
        qc = back(seg(t, h - .25, h + .1))
        if prop == 'crown':
            crown(cv, W / 2, lerp(300, 540, out3(seg(t, h - .25, h))), .75 * qc, a)
        if prop == 'cuffs':
            stamp(cv, t, h - .1, 'ARRESTED', W / 2, 520, 70, BAD, a)
        if v.get('role'):
            r_ = str(v['role']).upper()
            pill(cv, W / 2, 1210, r_, ACC, a * clamp(qc), size=fit(r_, 'black', 40, 900), fg=BG if ACC in (GOLD, UP) else WHITE)


def sc_date(cv, t, i, v, a):
    h = hit(i)
    q = back(seg(t, P(i), P(i) + .4))
    calendar(cv, W / 2, 640, 1.0 * q, a, str(v.get('month', '')).upper()[:9], str(v.get('day', '')), BAD if TONE != 'hype' else ACC)
    if v.get('event') and t >= h - .15:
        lines = wrap(str(v['event']).upper(), 16)[:3]
        for k, ln in enumerate(lines):
            p = back(seg(t, h - .15 + k * .1, h + .25 + k * .1))
            cv.text(W / 2, 1000 + k * 92, ln, 'black', fit(ln, 'black', 76, 980), TXT if k else ACC, a * clamp(p), anchor='cm', scale=max(.01, p))


def sc_chart(cv, t, i, v, a):
    if ch is None: return sc_title(cv, t, i, {'text': v.get('label', '')}, a)
    h = hit(i)
    k = CHART_SCENES.index(i)
    to = MARK[i]
    frm = MARK[CHART_SCENES[k - 1]] if k else max(0, min(to - 8, len(D['t']) // 5))
    f = keyframes(t, [(P(i), (frm + .999,)), (h + .1, (to + .999,))])[0]
    last = min(len(D['t']) - 1, int(f) + 6)
    x0 = 0
    lo = min(D['l'][x0:last + 1]); hi_ = max(D['h'][x0:last + 1]); pad = (hi_ - lo) * .12 or hi_ * .05
    ch.cam = (x0 - 1, max(last + 2, 20), max(0, lo - pad), hi_ + pad)
    chart_base(cv, t, ch, D, f, EP, SB['chart']['symbol'] + 'USD', SB['chart'].get('src', 'daily candles'), a,
               foot='Not financial advice · Data: ' + SB['chart'].get('src', 'exchange') + ' daily')
    if t >= h - .1 and v.get('label'):
        x, y = ch.X(to), ch.Y(D['c'][to])
        up = D['c'][to] >= D['c'][frm]
        left = x > 540
        callout(cv, x, y, x + (-40 if left else 40), (y - 170) if y > 700 else (y + 170), str(v['label']).upper(), ALT if up else BAD,
                seg(t, h - .1, h + .45) * a, size=32, side='left' if left else 'right')


def sc_versus(cv, t, i, v, a):
    h = hit(i)
    L, R = (v.get('left') or ['THEN', '?']), (v.get('right') or ['NOW', '?'])
    for side, (lab, val), t0, col in ((-1, L, P(i), MUTED), (1, R, h - .1, ACC)):
        q = back(seg(t, t0, t0 + .4))
        if q <= 0: continue
        x = W / 2 + side * 250
        cv.rect(x - 220 * q, 700 - 300 * q, x + 220 * q, 700 + 300 * q, PANEL, a, r=28)
        cv.rect(x - 220 * q, 700 - 300 * q, x + 220 * q, 700 - 300 * q + 10, col, a, r=4)
        cv.text(x, 520, str(lab).upper(), 'black', fit(str(lab).upper(), 'black', 44, 400), MUTED, a * clamp(q), anchor='cm', track=6)
        cv.text(x, 720, str(val).upper(), 'black', fit(str(val).upper(), 'black', 92, 400), col if side > 0 else TXT, a * clamp(q), anchor='cm', scale=max(.01, q), tnum=True)
    if t >= h - .1:
        p = seg(t, h - .1, h + .3)
        cv.text(W / 2, 700, '→', 'black', 90, ACC, a * p, anchor='cm')
    if v.get('note'):
        cv.text(W / 2, 1130, str(v['note']).upper(), 'black', fit(str(v['note']).upper(), 'black', 60, 980), ACC, a * seg(t, h + .3, h + .6), anchor='cm')


def sc_quote(cv, t, i, v, a):
    h = hit(i)
    q = back(seg(t, P(i), P(i) + .45))
    if q <= 0: return
    w, hh = 460 * q, 330 * q; cy = 760
    cv.rect(W / 2 - w, cy - hh, W / 2 + w, cy + hh, (245, 247, 250), a, r=30 * q)
    cv.circle(W / 2 - w + 80 * q, cy - hh + 80 * q, 46 * q, (60, 120, 230), a)
    cv.text(W / 2 - w + 145 * q, cy - hh + 62 * q, str(v.get('name', ''))[:26], 'black', max(6, int(38 * q)), (20, 24, 30), a, anchor='lm')
    cv.text(W / 2 - w + 145 * q, cy - hh + 106 * q, str(v.get('handle', ''))[:28], 'med', max(6, int(30 * q)), (110, 118, 130), a, anchor='lm')
    for k, ln in enumerate(wrap('“' + str(v.get('text', '')) + '”', 22)[:4]):
        cv.text(W / 2 - w + 60 * q, cy - 60 * q + k * 78 * q, ln, 'black', max(6, int(56 * q)), (20, 24, 30), a, anchor='lm')
    if t >= h - .1 and v.get('stamp'):
        stamp(cv, t, h - .1, str(v['stamp']).upper(), W / 2, 1230, 80, BAD, a)


def sc_list(cv, t, i, v, a):
    h = hit(i)
    items = [str(x).upper() for x in (v.get('items') or [])][:4]
    n = max(1, len(items))
    for k, it in enumerate(items):
        t0 = lerp(P(i) + .2, h, k / max(1, n - 1)) if n > 1 else h
        q = back(seg(t, t0 - .1, t0 + .3))
        if q <= 0: continue
        y = 560 + k * 190
        cv.rect(110, y - 70, W - 110, y + 70, PANEL, a, r=24)
        cv.circle(190, y, 40 * q, ACC if k == n - 1 else (60, 70, 92), a)
        cv.text(190, y, str(k + 1), 'black', 40, BG if k == n - 1 else TXT, a * clamp(q), anchor='cm')
        cv.text(260, y, it, 'black', fit(it, 'black', 54, 680), ACC if k == n - 1 else TXT, a * clamp(q), anchor='lm')



# ---------------------------------------------------------------- motion: several moments inside every scene
def scene_end(i):
    e = PARA[i][1]
    if CTA is not None: e = min(e, CTA)
    return e


def scene_beats(i):
    """every on-screen moment of scene i after its hit: the storyboard's beats on their words, plus automatic punch-ins
    so the picture never holds longer than PACE seconds"""
    h, e = hit(i), scene_end(i)
    ws = [w for w in cs.WORDS if w[0] == i and h + .45 < w[2] < e - .35]
    out = []
    for b in SCN[i].get('beats') or []:
        key = re.sub(r'[^\w$%]', '', str(b.get('word', ''))).lower()
        m = next((w for w in ws if w[1] == key and all(abs(w[2] - o['t']) > .7 for o in out)), None)
        if m is None and b.get('text'):                                   # word not found: give it the next free slot
            free = [w for w in ws if all(abs(w[2] - o['t']) > .9 for o in out) and w[2] > h + .9]
            m = free[len(free) // 2] if free else None
        if m: out.append({'t': m[2], 'text': str(b.get('text', '')).upper()[:22], 'icon': b.get('icon')})
    anchors = sorted([h] + [o['t'] for o in out] + [e])
    for a, b in zip(anchors, anchors[1:]):
        n = int((b - a) / PACE)
        for k in range(1, n + 1):
            tt = a + (b - a) * k / (n + 1)
            cand = [w for w in ws if abs(w[2] - tt) < .55 and (len(w[1]) >= 5 or re.search(r'\d', w[1]))]
            if cand: tt = min(cand, key=lambda w: abs(w[2] - tt))[2]
            out.append({'t': tt, 'text': '', 'icon': None})
    return sorted(out, key=lambda o: o['t'])


BEATS = [scene_beats(i) for i in range(len(SCN))]


def zsteps(t, i):
    """punch-in zoom: every hit/beat steps the camera closer (eased), the classic Shorts edit"""
    z = 0.0
    for k, tb in enumerate([hit(i)] + [b['t'] for b in BEATS[i]]):
        z += .028 * MOVE * out3(seg(t, tb - .04, tb + .28))
        z += .022 * MOVE * math.exp(-max(0.0, t - tb) * 9) * (t >= tb)  # a tiny overshoot kick
    return min(z, .16)


def scene_cam(t, i):
    s0, e = P(i), max(P(i) + .5, PARA[i][1])
    p = smooth(seg(t, s0, e))
    d = 1 if i % 2 == 0 else -1
    z = 1.0 + .035 * MOVE * p + zsteps(t, i)
    cx, cy = RW / 2 + d * 18 * K * (p - .5) * MOVE, RH * (.42 if i % 3 else .38)       # zoom toward the visual, not the captions
    M = np.array([[z, 0, cx - z * cx], [0, z, cy - z * cy], [0, 0, 1]], np.float64)
    if STYLE == '3d':                                                     # a slow camera orbit + a swing on every beat = depth
        sw = sum(math.exp(-max(0.0, t - b['t']) * 3) * (t >= b['t']) * (1 if n % 2 else -1) for n, b in enumerate(BEATS[i]))
        yaw = (.05 * d * (p - .5) + .025 * math.sin(t * .7) + .02 * sw) * MOVE
        pitch = (.035 + .015 * math.sin(t * .5 + i)) * MOVE
        src = np.float32([[0, 0], [RW, 0], [RW, RH], [0, RH]])
        ky, px = yaw * RH * .25, pitch * RW * .5                          # yaw: one side nearer; pitch: top leans away
        dst = np.float32([[px, -ky], [RW - px, ky], [RW + px * .3, RH - ky], [-px * .3, RH + ky]])
        dst = ((dst - [RW / 2, RH / 2]) * 1.06 + [RW / 2, RH / 2]).astype(np.float32)
        M = cv2.getPerspectiveTransform(src, dst).astype(np.float64) @ M
    return M


STICK_Y = 1410


def overlay(cv, t, i):
    """beat stickers: short facts that pop in on their word, alternate sides, leave when the next one comes"""
    bs = BEATS[i]; a_sc = 1.0 if i == len(SCN) - 1 else fade(t, i)
    shown = [b for b in bs if b['text']]
    for n, b in enumerate(shown):
        t0 = b['t']; t1 = shown[n + 1]['t'] if n + 1 < len(shown) else scene_end(i)
        if not (t0 - .05 <= t < t1): continue
        q = back(seg(t, t0 - .05, t0 + .3)); out = seg(t, t1 - .2, t1)
        x = W / 2 + (-150 if n % 2 == 0 else 150) * (len(shown) > 1)
        y = STICK_Y + 10 * math.sin((t - t0) * 2.2)                       # sticker floats
        sz = fit(b['text'], 'black', 50, 780)
        tw, _ = text_size(b['text'], 'black', sz, track=3)
        ic = b.get('icon') if b.get('icon') in ICON_NAMES else None
        wbox = tw + 70 + (90 if ic else 0)
        x = min(max(x, wbox / 2 + 40), W - wbox / 2 - 40)
        s_ = max(.01, q * (1 - out))
        col = ACC if n % 2 == 0 else ALT
        cv.rect(x - wbox / 2 * s_, y - 52 * s_, x + wbox / 2 * s_, y + 52 * s_, col, a_sc * clamp(q) * (1 - out), r=52 * s_)
        if ic: icon(cv, ic, x - wbox / 2 * s_ + 70 * s_, y, .22 * s_, a_sc * (1 - out), t)
        cv.text(x + (45 if ic else 0) * s_, y, b['text'], 'black', sz, BG if col in (GOLD, UP) else WHITE, a_sc * clamp(q) * (1 - out),
                anchor='cm', scale=s_, track=3)
    for b in bs:                                                          # every moment also flashes a light burst
        g = seg(t, b['t'] - .02, b['t'] + .35)
        if 0 < g < 1:
            r = lerp(120, 520, out3(g))
            cv.ring(W / 2, 760, r, ACC, 6 * (1 - g) + 1, .35 * (1 - g) * a_sc)
    if i == 0:                                                            # branded sting over the hook (no delay before the hook)
        g = seg(t, .05, .6); g2 = 1 - seg(t, 2.2, 2.6)
        if g2 > 0:
            q = back(g)
            txt = 'CHAIN SECRETS' + (f'  ·  #{EP}' if EP else '')
            tw, _ = text_size(txt, 'black', 30, track=6)
            cv.rect(W / 2 - (tw / 2 + 36) * q, 232 - 30 * q, W / 2 + (tw / 2 + 36) * q, 232 + 30 * q, (14, 18, 28), .82 * g2, r=30 * q)
            cv.text(W / 2, 232, txt, 'black', 30, GOLD, g2 * clamp(q), anchor='cm', scale=max(.01, q), track=6)
            sx = lerp(W / 2 - tw / 2 - 60, W / 2 + tw / 2 + 60, seg(t, .5, 1.1))   # light sweep across the badge
            if .5 < t < 1.1: cv.glow(sx, 232, 50, WHITE, .35 * g2)


TEMPLATES = {'title': sc_title, 'counter': sc_counter, 'stamp': sc_stamp, 'person': sc_person, 'date': sc_date, 'chart': sc_chart,
             'versus': sc_versus, 'quote': sc_quote, 'list': sc_list}


def make_scene(i):
    v = SCN[i]['visual']; fn = TEMPLATES[v['type']]
    last = i == len(SCN) - 1

    def scene(cv, t):
        a = 1.0 if last else fade(t, i)
        if i == 0:
            a = 1 - seg(t, P(1) - .2, P(1)) if len(SCN) > 1 else 1.0
        ambient(cv, t)
        fn(cv, t, i, v, a)
    return scene


cs.SCENES = [make_scene(i) for i in range(len(SCN))]
cs.IMPACTS = [hit(i) for i, s in enumerate(SCN) if s['role'] in PACK['impacts'] and s['visual']['type'] in ('title', 'stamp', 'counter', 'chart', 'versus', 'quote', 'person')]
cs.NAME = 'auto'
cs.SCENE_CAM = scene_cam
cs.BACKDROP = backdrop if MEDIA else None
cs.OVERLAY = overlay


# ---------------------------------------------------------------- sound design (procedural, keyed to the same hits)
def make_sfx(out):
    from sfx import SR, boom, thud, whoosh, riser, ding, tick, pop, glitch, sweep, place, write
    import numpy as np
    k = {'funny': 1.0, 'serious': .7, 'mystery': .8, 'hype': 1.1}[TONE]
    tr = np.zeros((int(DUR * SR), 2))
    for j, p in enumerate(PARA[1:]):
        place(tr, whoosh(.4, j % 2 == 0, .09 * k), p[0] - .12, pan=(.4 if j % 2 else -.4))
    place(tr, pop(.3 * k, 600), .05)
    for i, s in enumerate(SCN):
        h, ty = hit(i), s['visual']['type']
        big = s['role'] in ('twist', 'payoff', 'hook')
        if TONE == 'mystery' and s['role'] == 'twist': place(tr, riser(.9, .12), h - .9)
        if ty == 'counter':
            for n in range(14): place(tr, tick(.08 * k), h - .2 + .9 * n / 14, pan=((n % 5) - 2) * .15)
            place(tr, ding(1760, .7, .15 * k), h + .75)
        elif ty in ('stamp', 'title'):
            place(tr, thud(.4, .5 * k), h)
            if big and TONE != 'serious': place(tr, boom(1.1, 80, 30, .55 * k), h)
            if TONE == 'funny' and s['role'] == 'twist': place(tr, glitch(.45, .2), h)
        elif ty == 'chart':
            for n in range(16): place(tr, tick(.07 * k), P(i) + .1 + (h - P(i)) * n / 16, pan=((n % 5) - 2) * .15)
            place(tr, pop(.2 * k, 650), h)
            if big: place(tr, boom(1.0, 80, 30, .5 * k), h)
        elif ty == 'person':
            place(tr, pop(.2 * k, 600), P(i) + .1); place(tr, ding(1568, .9, .15 * k), h)
        elif ty == 'date':
            place(tr, pop(.2 * k, 700), P(i) + .1); place(tr, thud(.35, .35 * k), h)
        elif ty == 'versus':
            place(tr, sweep(.8, True, .12 * k), h - .5); place(tr, thud(.4, .45 * k), h)
        elif ty == 'quote':
            place(tr, pop(.25 * k, 800), P(i) + .1)
            if s['visual'].get('stamp'): place(tr, thud(.4, .5 * k), h)
        elif ty == 'list':
            n = len(s['visual'].get('items') or [1])
            for j in range(n): place(tr, pop(.2 * k, 600 + 80 * j), lerp(P(i) + .2, h, j / max(1, n - 1)) if n > 1 else h)
    for i in range(len(SCN)):                                             # every on-screen moment gets a soft accent
        for n, b in enumerate(BEATS[i]):
            if b['text']: place(tr, pop(.16 * k, 720 + 90 * (n % 3)), b['t'] - .02); place(tr, whoosh(.25, n % 2 == 0, .05 * k), b['t'] - .12)
            else: place(tr, whoosh(.3, n % 2 == 0, .045 * k), b['t'] - .12, pan=(.3 if n % 2 else -.3))
    C = CTA
    if C is not None:
        place(tr, whoosh(.5, True, .14), C - .1); place(tr, thud(.4, .45), C + .2); place(tr, ding(1760, 1.0, .2), C + .5)
    place(tr, whoosh(.6, False, .3), DUR - .6)
    write(out, tr * SFX_K if SFX_K else tr * 0)


if __name__ == '__main__':
    cmd = sys.argv[2] if len(sys.argv) > 2 else 'full'
    if cmd == 'stills':
        from PIL import Image
        ims = [Image.fromarray(frame(float(s))).resize((360, 640), Image.LANCZOS) for s in sys.argv[3:]]
        cols = 6
        sheet = Image.new('RGB', (360 * min(cols, len(ims)), 640 * ((len(ims) + cols - 1) // cols)))
        for n, im in enumerate(ims): sheet.paste(im, ((n % cols) * 360, (n // cols) * 640))
        sheet.save(os.path.join(JOB, 'sheet.png'))
    elif cmd == 'part':
        a, b = int(sys.argv[3]), int(sys.argv[4])
        encode(frame, DUR, os.path.join(JOB, f'part_{a:05d}.mp4'), fps=int(os.environ.get('FPS', 60)), crf=18, start=a, end=b)
    elif cmd == 'sfx':
        make_sfx(os.path.join(JOB, 'sfx.wav'))
    elif cmd == 'info':
        print(json.dumps({'dur': DUR, 'frames': int(round(DUR * int(os.environ.get('FPS', 60))))}))
