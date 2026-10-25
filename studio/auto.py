"""Automatic Chain Secrets Short: renders any storyboard with the house engine (cs.py + engine.py + kit20.py).

python auto.py JOBDIR stills 1.0 4.5 ...    -> JOBDIR/sheet.png (preview frames)
python auto.py JOBDIR part A B              -> JOBDIR/part_A.mp4 (frames A..B)
python auto.py JOBDIR sfx                   -> JOBDIR/sfx.wav

JOBDIR holds storyboard.json, timing.json and (if the story has a chart) data.json with real daily candles.
Every scene is one of the template types below; its punch lands on the scene's "hit" word (B['s<i>'])."""
import os, sys, json, math
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


def hit(i): return B.get(f's{i}', P(i) + .4)


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


def icon(cv, name, x, y, s, a, t=0.0):
    if a <= 0 or s <= .02: return
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
    else:
        cv.glow(x, y, 160 * s, ACC, .2 * a); cv.text(x, y, '?', 'black', max(6, int(260 * s)), ACC, a, anchor='cm')


# ---------------------------------------------------------------- scene templates
def sc_title(cv, t, i, v, a):
    h = hit(i)
    ic = v.get('icon')
    if ic: icon(cv, ic, W / 2, 620, back(seg(t, P(i), P(i) + .4)) * .9, a * (1 - .4 * seg(t, h, h + .3)), t)
    lines = wrap(str(v.get('text', '')).upper(), 12)[:3] or ['']
    y0 = 1000 if ic else 860
    if t >= h - .05:
        for k, ln in enumerate(lines):
            size = fit(ln, 'black', 150, 980)
            slam(cv, t, h - .05 + k * .12, ln, y0 + k * size * 1.02, size, ACC if k == len(lines) - 1 else TXT, a)
        if v.get('sub'):
            cv.text(W / 2, y0 + len(lines) * 150 + 10, str(v['sub']).upper(), 'xbold', fit(str(v['sub']).upper(), 'xbold', 46, 960), MUTED,
                    a * seg(t, h + .3, h + .6), anchor='cm', track=4)


def fmt_num(v, pre, suf):
    if abs(v) >= 100: s = f'{v:,.0f}'
    elif abs(v) >= 10: s = f'{v:,.1f}'.rstrip('0').rstrip('.')
    else: s = f'{v:,.2f}'.rstrip('0').rstrip('.')
    return f'{pre}{s}{suf}'


def sc_counter(cv, t, i, v, a):
    h = hit(i)
    try: val = float(str(v.get('value', 0)).replace(',', '').replace('$', ''))
    except ValueError: val = 0
    pre, suf = str(v.get('prefix', '')), str(v.get('suffix', ''))
    ic = v.get('icon') or ('bitcoin' if 'BTC' in suf.upper() else None)
    if ic: icon(cv, ic, W / 2, 640, back(seg(t, P(i), P(i) + .4)) * .85, a, t)
    p = out3(seg(t, h - .25, h + .75))
    s = fmt_num(val * p, pre, suf)
    size = fit(fmt_num(val, pre, suf), 'black', 130, 1000)
    counter(cv, s, 1010 if ic else 880, size, ALT if val >= 0 else BAD, a * clamp(seg(t, h - .3, h - .1) * 3 + (p > 0)))
    if v.get('label'):
        cv.text(W / 2, (1010 if ic else 880) + size * .85, str(v['label']).upper(), 'black', fit(str(v['label']).upper(), 'black', 46, 960), MUTED,
                a * seg(t, h + .4, h + .7), anchor='cm', track=10)


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
    if prop == 'officer': officer(cv, W / 2, 760, 1.4 * q, a)
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


TEMPLATES = {'title': sc_title, 'counter': sc_counter, 'stamp': sc_stamp, 'person': sc_person, 'date': sc_date, 'chart': sc_chart,
             'versus': sc_versus, 'quote': sc_quote, 'list': sc_list}


def make_scene(i):
    v = SCN[i]['visual']; fn = TEMPLATES[v['type']]
    last = i == len(SCN) - 1

    def scene(cv, t):
        a = 1.0 if last else fade(t, i)
        if i == 0:
            a = 1 - seg(t, P(1) - .2, P(1)) if len(SCN) > 1 else 1.0
        fn(cv, t, i, v, a)
    return scene


cs.SCENES = [make_scene(i) for i in range(len(SCN))]
cs.IMPACTS = [hit(i) for i, s in enumerate(SCN) if s['role'] in PACK['impacts'] and s['visual']['type'] in ('title', 'stamp', 'counter', 'chart', 'versus', 'quote', 'person')]
cs.NAME = 'auto'


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
    C = CTA
    place(tr, whoosh(.5, True, .14), C - .1); place(tr, thud(.4, .45), C + .2); place(tr, ding(1760, 1.0, .2), C + .5)
    place(tr, whoosh(.6, False, .3), DUR - .6)
    write(out, tr)


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
