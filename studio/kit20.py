"""Shared props for Shorts #15-#21 (v20-v26). Import after cs.load(...): `from kit20 import *`."""
import math, datetime
from cs import *

def dfmt(D):
    return lambda i: datetime.datetime.fromtimestamp(D['t'][i], datetime.UTC).strftime('%b %d, %Y').upper()

def chart_base(cv, t, ch, D, f, ep, symbol, sub, a, foot='Not financial advice · Data: Bitstamp BTC/USD', dot=True):
    """grid + candles up to f (float index) + price tag + live dot + header. returns (last, close)."""
    last, u = int(f), f - int(f)
    ch.grid(cv, alpha=a)
    ch.candles(cv, last, u, alpha=a)
    o, h, l, c = ch.ohlc(last, u)
    col = UP if c >= o else DN
    ch.price_tag(cv, c, col, a)
    if dot:
        cv.glow(ch.X(last), ch.Y(c), 28, col, .5 * a); cv.circle(ch.X(last), ch.Y(c), 8, WHITE, a)
    header(cv, 'CHAIN SECRETS', ep, symbol, sub, c, col, dfmt(D)(last), tf='1D', alpha=a)
    footer(cv, foot)
    return last, c

def idx(D, ymd):
    ts = int(datetime.datetime.strptime(ymd, '%Y-%m-%d').replace(tzinfo=datetime.UTC).timestamp())
    return D['t'].index(ts)

def bracket(cv, xa, xb, y, q, label, col, a):
    if q <= 0: return
    xe = lerp(xa, xb, out3(q))
    cv.line([(xa, y + 18), (xa, y), (xe, y), (xe, y + 18)], col, 5, a * clamp(q * 3))
    if q > .5:
        tw, _ = text_size(label, 'black', 32); mx = (xa + xb) / 2
        cv.rect(mx - tw / 2 - 20, y - 54, mx + tw / 2 + 20, y - 8, col, a, r=23)
        cv.text(mx, y - 31, label, 'black', 32, BG, a, anchor='cm')

def pill(cv, x, y, text, col, a, size=40, fg=WHITE, s=1.0):
    if a <= 0 or s <= .01: return
    tw, th = text_size(text, 'black', size)
    w, h = (tw + 56) * s, (th + 36) * s
    cv.rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, col, a, r=h / 2)
    cv.text(x, y, text, 'black', size, fg, a, anchor='cm', scale=s)

def person(cv, x, y, s, col, a):
    """silhouette, (x,y) = shoulders center; ~ 300*s tall"""
    if a <= 0 or s <= .01: return
    cv.circle(x, y - 70 * s, 58 * s, col, a)
    cv.rect(x - 85 * s, y, x + 85 * s, y + 200 * s, col, a, r=60 * s)

def padlock(cv, x, y, s, a, col=GOLD, open_=0.0):
    if a <= 0 or s <= 0: return
    cv.ring(x, y - 40 * s - 40 * s * open_, 42 * s, col, 14 * s, a)
    cv.rect(x - 70 * s, y - 40 * s, x + 70 * s, y + 70 * s, col, a, r=14 * s)
    cv.circle(x, y + 10 * s, 14 * s, BG, a); cv.rect(x - 6 * s, y + 10 * s, x + 6 * s, y + 44 * s, BG, a)

def bars(cv, a, x0=0, x1=W, y0=0, y1=H, n=7, col=(120, 128, 146)):
    if a <= 0: return
    for k in range(n):
        x = x0 + (x1 - x0) * (k + .5) / n
        cv.rect(x - 14, y0, x + 14, y1, col, a, r=8)
        cv.rect(x - 14, y0, x - 4, y1, (170, 178, 196), a * .6, r=4)
    cv.rect(x0, y0 + 60, x1, y0 + 90, col, a)

def plane(cv, x, y, s, a, col=TXT, ang=0.0):
    if a <= 0 or s <= .01: return
    c, n = math.cos(ang), math.sin(ang)
    R = lambda u, v: (x + (u * c - v * n) * s, y + (u * n + v * c) * s)
    cv.poly([R(-140, -16), R(120, -16), R(160, 0), R(120, 16), R(-140, 16)], col, a)
    cv.poly([R(-10, -14), R(40, -14), R(-30, -120), R(-60, -120)], col, a)
    cv.poly([R(-10, 14), R(40, 14), R(-30, 120), R(-60, 120)], col, a)
    cv.poly([R(-140, -14), R(-110, -14), R(-130, -60), R(-150, -60)], col, a)

def polaroid(cv, x, y, s, a, rot=0.0, inner=(40, 46, 60), label=None, lcol=MUTED):
    if a <= 0 or s <= .01: return
    c, n = math.cos(rot), math.sin(rot)
    R = lambda u, v: (x + (u * c - v * n) * s, y + (u * n + v * c) * s)
    cv.poly([R(-170, -190), R(170, -190), R(170, 210), R(-170, 210)], (236, 232, 222), a)
    cv.poly([R(-145, -165), R(145, -165), R(145, 120), R(-145, 120)], inner, a)
    if label: cv.text(*R(0, 165), label, 'black', int(30 * s) or 1, lcol, a, anchor='cm')

def popcorn_tin(cv, x, y, s, a, lid=0.0, t=0.0):
    """Cheetos-style orange popcorn tin. lid 0 closed .. 1 off"""
    if a <= 0 or s <= .01: return
    w, h = 170 * s, 300 * s
    cv.glow(x, y, 260 * s, (255, 140, 30), .18 * a)
    cv.rect(x - w, y - h / 2, x + w, y + h / 2, (240, 120, 24), a, r=20 * s)
    cv.rect(x - w, y - h / 2 + 40 * s, x + w, y - h / 2 + 64 * s, (255, 196, 46), a)
    cv.rect(x - w, y + h / 2 - 64 * s, x + w, y + h / 2 - 40 * s, (255, 196, 46), a)
    cv.text(x, y + 10 * s, 'POPCORN', 'black', max(8, int(54 * s)), WHITE, a, anchor='cm')
    ly = y - h / 2 - 14 * s - 220 * s * out3(lid); lx = x + 260 * s * out3(lid)
    cv.rect(lx - w - 10 * s, ly - 16 * s, lx + w + 10 * s, ly + 14 * s, (210, 96, 18), a * (1 - seg(lid, .4, .9)), r=10 * s)

def board(cv, x, y, s, a, t=0.0):
    """tiny single-board computer"""
    if a <= 0 or s <= .01: return
    cv.glow(x, y, 160 * s, UP, .25 * a)
    cv.rect(x - 120 * s, y - 80 * s, x + 120 * s, y + 80 * s, (22, 110, 70), a, r=10 * s)
    cv.rect(x - 40 * s, y - 34 * s, x + 30 * s, y + 34 * s, (30, 30, 36), a, r=4 * s)
    for k in range(10): cv.rect(x - 110 * s + k * 22 * s, y - 76 * s, x - 100 * s + k * 22 * s, y - 64 * s, GOLD, a)
    cv.rect(x + 60 * s, y - 50 * s, x + 118 * s, y - 10 * s, (180, 186, 196), a, r=3 * s)
    cv.rect(x + 60 * s, y + 10 * s, x + 118 * s, y + 50 * s, (180, 186, 196), a, r=3 * s)
    cv.circle(x - 90 * s, y + 50 * s, 8 * s, DN if int(t * 3) % 2 else UP, a)

def safe(cv, x, y, s, a, door=0.0):
    if a <= 0 or s <= .01: return
    cv.rect(x - 160 * s, y - 150 * s, x + 160 * s, y + 150 * s, (90, 98, 116), a, r=18 * s)
    cv.rect(x - 130 * s, y - 120 * s, x + 130 * s, y + 120 * s, (60, 66, 82), a, r=12 * s)
    cv.ring(x, y, 52 * s, (170, 178, 196), 12 * s, a)
    for k in range(4):
        an = k * math.pi / 2 + door * 3
        cv.line([(x, y), (x + 52 * s * math.cos(an), y + 52 * s * math.sin(an))], (170, 178, 196), 8 * s, a)

def floorboards(cv, y, a, gap=0.0):
    for k in range(6):
        x = k * 190 - 20
        off = (-1 if k < 3 else 1) * gap * (260 if k in (2, 3) else 0)
        cv.rect(x + off + 4, y, x + off + 186, y + 70, (120, 82, 50), a, r=4)
        cv.line([(x + off + 20, y + 35), (x + off + 160, y + 35)], (100, 66, 38), 3, a)

def house(cv, x, y, s, a, col=(60, 70, 92), win=GOLD):
    if a <= 0 or s <= .01: return
    cv.poly([(x - 260 * s, y - 120 * s), (x, y - 300 * s), (x + 260 * s, y - 120 * s)], (80, 90, 114), a)
    cv.rect(x - 220 * s, y - 120 * s, x + 220 * s, y + 160 * s, col, a)
    cv.rect(x - 40 * s, y + 20 * s, x + 40 * s, y + 160 * s, (40, 46, 62), a, r=6 * s)
    for dx in (-140, 100):
        cv.rect(x + dx * s, y - 70 * s, x + (dx + 60) * s, y - 10 * s, win, a, r=4 * s)

def townhouse(cv, x, y, s, a, lit=1.0):
    """tall 4-floor brownstone; (x,y) bottom center"""
    if a <= 0 or s <= .01: return
    w, h = 300 * s, 760 * s
    cv.rect(x - w, y - h, x + w, y, (96, 62, 48), a, r=6 * s)
    cv.rect(x - w - 16 * s, y - h - 30 * s, x + w + 16 * s, y - h, (70, 44, 34), a)
    for fl in range(4):
        for k in range(3):
            wx = x + (k - 1) * 180 * s; wy = y - h + 70 * s + fl * 165 * s
            lit_k = lit if (fl + k) % 3 else lit * .35
            cv.rect(wx - 50 * s, wy, wx + 50 * s, wy + 110 * s, (40, 44, 58), a, r=4 * s)
            cv.rect(wx - 42 * s, wy + 8 * s, wx + 42 * s, wy + 102 * s, GOLD, a * .85 * lit_k, r=3 * s)
    cv.rect(x - 70 * s, y - 150 * s, x + 70 * s, y, (40, 30, 26), a, r=6 * s)
    cv.rect(x - 110 * s, y - 20 * s, x + 110 * s, y, (120, 110, 104), a)

def doge(cv, x, y, r, a=1.0):
    if r < 2 or a <= 0: return
    cv.glow(x, y, r * 1.5, (200, 166, 50), .25 * a)
    cv.circle(x, y, r, (196, 160, 52), a); cv.circle(x, y, r * .82, (226, 192, 84), a)
    cv.text(x, y, 'Ð', 'black', max(6, int(r * 1.1)), WHITE, a, anchor='cm')

def crown(cv, x, y, s, a, col=GOLD):
    if a <= 0 or s <= .01: return
    cv.glow(x, y, 200 * s, col, .25 * a)
    cv.poly([(x - 150 * s, y + 60 * s), (x - 150 * s, y - 70 * s), (x - 75 * s, y), (x, y - 100 * s),
             (x + 75 * s, y), (x + 150 * s, y - 70 * s), (x + 150 * s, y + 60 * s)], col, a)
    for dx, dy in ((-150, -70), (0, -100), (150, -70)): cv.circle(x + dx * s, y + dy * s, 18 * s, col, a)
    for k, cc in enumerate((DN, BLUE, UP)): cv.circle(x + (k - 1) * 80 * s, y + 30 * s, 14 * s, cc, a)

def tweet(cv, x, y, s, a, name, handle, text, size=54):
    if a <= 0 or s <= .01: return
    w, h = 420 * s, 170 * s
    cv.rect(x - w, y - h, x + w, y + h, (245, 247, 250), a, r=26 * s)
    cv.circle(x - w + 70 * s, y - h + 70 * s, 40 * s, (60, 120, 230), a)
    cv.text(x - w + 130 * s, y - h + 52 * s, name, 'black', max(6, int(34 * s)), (20, 24, 30), a, anchor='lm')
    cv.text(x - w + 130 * s, y - h + 92 * s, handle, 'med', max(6, int(28 * s)), (110, 118, 130), a, anchor='lm')
    cv.text(x - w + 50 * s, y + 50 * s, text, 'black', max(6, int(size * s)), (20, 24, 30), a, anchor='lm')

def sign_closed(cv, x, y, s, a, rot=0.0):
    if a <= 0 or s <= .01: return
    c, n = math.cos(rot), math.sin(rot)
    cv.line([(x - 150 * s, y - 120 * s), (x, y - 220 * s), (x + 150 * s, y - 120 * s)], (150, 158, 176), 6 * s, a)
    cv.rect(x - 380 * s, y - 120 * s, x + 380 * s, y + 120 * s, DN, a, r=20 * s)
    cv.text(x, y - 40 * s, 'TEMPORARILY', 'black', max(6, int(60 * s)), WHITE, a, anchor='cm')
    cv.text(x, y + 45 * s, 'CLOSED', 'black', max(6, int(96 * s)), WHITE, a, anchor='cm', track=8)

def calendar(cv, x, y, s, a, month, day, col=DN):
    if a <= 0 or s <= .01: return
    cv.rect(x - 150 * s, y - 150 * s, x + 150 * s, y + 160 * s, (236, 232, 222), a, r=22 * s)
    cv.rect(x - 150 * s, y - 150 * s, x + 150 * s, y - 70 * s, col, a, r=22 * s)
    cv.rect(x - 150 * s, y - 100 * s, x + 150 * s, y - 70 * s, col, a)
    cv.text(x, y - 110 * s, month, 'black', max(6, int(46 * s)), WHITE, a, anchor='cm', track=6)
    cv.text(x, y + 45 * s, str(day), 'black', max(6, int((150 if len(str(day)) <= 2 else 92) * s)), (30, 34, 46), a, anchor='cm', tnum=True)

def dunes(cv, y, a, t=0.0):
    for k, col in enumerate(((150, 110, 64), (176, 132, 78), (200, 156, 96))):
        yy = y + k * 110
        for j in range(5):
            cx = -100 + j * 300 + (k % 2) * 150
            cv.circle(cx, yy + 160, 260, col, a)
        cv.rect(0, yy + 160, W, 1560, col, a)

def car(cv, x, y, s, a, col=(230, 234, 242)):
    if a <= 0 or s <= .01: return
    cv.rect(x - 170 * s, y - 50 * s, x + 170 * s, y + 30 * s, col, a, r=24 * s)
    cv.rect(x - 100 * s, y - 110 * s, x + 80 * s, y - 40 * s, col, a, r=24 * s)
    cv.rect(x - 85 * s, y - 98 * s, x - 10 * s, y - 52 * s, (40, 60, 90), a, r=8 * s)
    cv.rect(x + 2 * s, y - 98 * s, x + 66 * s, y - 52 * s, (40, 60, 90), a, r=8 * s)
    for dx in (-100, 100): cv.circle(x + dx * s, y + 32 * s, 38 * s, (30, 32, 40), a); cv.circle(x + dx * s, y + 32 * s, 16 * s, (150, 158, 176), a)

def badge_id(cv, x, y, s, a, top, mid, col=GOLD):
    """agent ID wallet: star badge + card"""
    if a <= 0 or s <= .01: return
    cv.rect(x - 300 * s, y - 180 * s, x + 300 * s, y + 180 * s, (40, 30, 26), a, r=24 * s)
    pts = []
    for k in range(10):
        r_ = (120 if k % 2 == 0 else 55) * s; an = -math.pi / 2 + k * math.pi / 5
        pts.append((x - 150 * s + r_ * math.cos(an), y + r_ * math.sin(an)))
    cv.glow(x - 150 * s, y, 160 * s, col, .25 * a)
    cv.poly(pts, col, a)
    cv.rect(x + 10 * s, y - 130 * s, x + 270 * s, y + 130 * s, (236, 232, 222), a, r=12 * s)
    cv.text(x + 140 * s, y - 70 * s, top, 'black', max(6, int(56 * s)), (30, 50, 110), a, anchor='cm')
    cv.text(x + 140 * s, y + 10 * s, mid, 'xbold', max(6, int(24 * s)), (60, 66, 80), a, anchor='cm')
    for k in range(2): cv.rect(x + 40 * s, y + (50 + k * 30) * s, x + (240 - k * 60) * s, y + (62 + k * 30) * s, (190, 186, 176), a, r=4 * s)

def officer(cv, x, y, s, a):
    """traffic officer: person in hi-vis vest with cap"""
    if a <= 0 or s <= .01: return
    person(cv, x, y, s, (40, 70, 140), a)
    cv.rect(x - 85 * s, y + 10 * s, x + 85 * s, y + 150 * s, (220, 240, 60), a, r=30 * s)
    cv.rect(x - 85 * s, y + 70 * s, x + 85 * s, y + 90 * s, (230, 234, 242), a)
    cv.rect(x - 64 * s, y - 140 * s, x + 64 * s, y - 108 * s, (30, 44, 90), a, r=10 * s)
    cv.rect(x - 30 * s, y - 112 * s, x + 90 * s, y - 100 * s, (30, 44, 90), a, r=6 * s)

def laptop(cv, x, y, s, a, glow=0.0):
    if a <= 0 or s <= .01: return
    cv.rect(x - 160 * s, y - 210 * s, x + 160 * s, y, (170, 178, 196), a, r=14 * s)
    cv.rect(x - 140 * s, y - 192 * s, x + 140 * s, y - 18 * s, (24, 30, 44), a, r=8 * s)
    if glow > 0:
        cv.text(x, y - 105 * s, '* * * * * *', 'black', max(6, int(40 * s)), GOLD, a * glow, anchor='cm')
    cv.rect(x - 200 * s, y, x + 200 * s, y + 24 * s, (140, 148, 166), a, r=10 * s)
