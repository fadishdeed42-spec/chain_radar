"""Chain Secrets shared video toolkit: helpers, post FX, frame loop, CLI."""
import sys, os, math, json
os.environ.setdefault('CS_SCALE', str(4 / 3))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, cv2
import engine
from engine import *
engine.FONTS['mono'] = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
_glow0 = Canvas.glow
def _qglow(self, x, y, r, color, alpha=0.5, sigma=None):
    if r > 30: r = round(math.exp(round(math.log(r) / .06) * .06))   # quantize radius -> blur cache hits
    return _glow0(self, x, y, r, color, alpha, sigma)
Canvas.glow = _qglow

HERE = os.path.dirname(os.path.abspath(__file__))
CH = DUR = B = PARA = CAPS = CTA = CTA2 = None
def load(path):
    global CH, DUR, B, PARA, CAPS, CTA, CTA2
    T_ = json.load(open(path))
    CH, DUR, B, PARA, CAPS = T_['chunks'], T_['dur'], T_['beats'], T_['para'], T_['caps']
    CTA = T_.get('cta'); CTA2 = T_.get('cta2')   # end card start (set in the timing file); drawn by cta_layer over the last scene
def P(i): return PARA[i][0]
COIN = (247, 147, 26); COIN_L = (255, 190, 80); TERM = (60, 230, 120)

from PIL import Image as _Im
_logo = np.asarray(_Im.open(f'{HERE}/chain_secrets_profile.png').convert('RGB').resize((400, 400), _Im.LANCZOS), np.float32)
_yy, _xx = np.mgrid[0:400, 0:400]
_lmask = np.clip(200 - np.sqrt((_xx - 199.5) ** 2 + (_yy - 199.5) ** 2), 0, 1).astype(np.float32)
def logo(cv, cx, cy, scale, alpha):
    if alpha <= 0.01 or scale <= 0.05: return
    sz = max(2, int(300 * scale * K))
    im = cv2.resize(_logo, (sz, sz), interpolation=cv2.INTER_AREA)
    m = cv2.resize(_lmask, (sz, sz)) * alpha
    x0, y0 = int(cx * K - sz / 2), int(cy * K - sz / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(RW, x0 + sz), min(RH, y0 + sz)
    roi = cv.a[ya:yb, xa:xb]; mm = m[ya - y0:yb - y0, xa - x0:xb - x0, None]
    roi += (im[ya - y0:yb - y0, xa - x0:xb - x0] - roi) * mm

def coin(cv, x, y, r, a=1.0, rot=0.0):
    if r < 2 or a <= 0: return
    sq = abs(math.cos(rot)) * .85 + .15
    cv.glow(x, y, r * 1.6, COIN, .25 * a)
    cv.poly([(x + r * sq * math.cos(k / 24 * 6.2832), y + r * math.sin(k / 24 * 6.2832)) for k in range(24)], COIN, a)
    cv.poly([(x + r * .8 * sq * math.cos(k / 24 * 6.2832), y + r * .8 * math.sin(k / 24 * 6.2832)) for k in range(24)], COIN_L, a)
    if sq > .45: cv.text(x, y, '₿', 'black', max(6, int(r * 1.05)), WHITE, a, anchor='cm', scale=sq)

def stamp(cv, t, t0, text, x, y, size=120, col=DN, alpha=1.0):
    p = seg(t, t0, t0 + .3)
    if p <= 0 or alpha <= 0: return
    s = lerp(2.6, 1, out5(p)); a = clamp(p * 3) * alpha
    tw, th = text_size(text, 'black', size, track=6)
    w, h = (tw + 70) * s, (th + 46) * s
    cv.rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, col, .14 * a, r=18 * s)
    for (ax, ay, bx, by) in ((-1, -1, 1, -1), (-1, 1, 1, 1), (-1, -1, -1, 1), (1, -1, 1, 1)):
        cv.line([(x + ax * w / 2, y + ay * h / 2), (x + bx * w / 2, y + by * h / 2)], col, 9, a)
    cv.text(x, y, text, 'black', size, col, a, anchor='cm', scale=s, track=6)

def slam(cv, t, t0, text, y, size, col, alpha=1.0, sub=None, subcol=TXT):
    p = seg(t, t0, t0 + .22)
    if p <= 0 or alpha <= 0: return
    cv.text(W / 2, y, text, 'black', size, col, clamp(p * 3) * alpha, anchor='cm', scale=lerp(1.9, 1, out5(p)), shadow=10)
    if sub: cv.text(W / 2, y + size * .72, sub, 'xbold', 44, subcol, alpha * seg(t, t0 + .2, t0 + .45), anchor='cm')

def counter(cv, s, y, size, col, alpha=1.0, glow=True, x=W / 2):
    if glow: cv.glow(x, y, size * 1.3, col, .16 * alpha)
    cv.text(x, y, s, 'black', size, col, alpha, anchor='cm', tnum=True, shadow=10)

def caption_layer(cv, t):
    for k, (ci, text, hl) in enumerate(CAPS):
        a0, a1 = CH[ci]
        nxt = CH[CAPS[k + 1][0]][0] - .05 if k + 1 < len(CAPS) else 1e9
        if a0 - .05 <= t < min(a1 + .3, nxt):
            n = len(text.split(' '))
            al = (1 - seg(t, a1 + .12, a1 + .3)) * (1 - seg(t, nxt - .07, nxt))
            pop_words(cv, t, a0 - .05, text, 1690, 58, kind='black', hl={k: tuple(v) for k, v in hl.items()},
                      per=max(.035, (a1 - a0) * .8 / max(1, n)), alpha=al, max_w=1000)

def badge(cv, t, t0, text, y=290, col=GOLD, alpha=1.0, fg=BG):
    p = back(seg(t, t0, t0 + .4))
    if p <= 0: return
    tw, _ = text_size(text, 'black', 46, track=3)
    w = (tw + 70) * p
    cv.rect(W / 2 - w / 2, y - 40 * p, W / 2 + w / 2, y + 40 * p, col, alpha, r=40 * p)
    cv.text(W / 2, y, text, 'black', 46, fg, alpha, anchor='cm', scale=max(p, .01), track=3)

def fade(t, i): return out3(seg(t, P(i), P(i) + .25)) * (1 - seg(t, PARA[i][1] - .2, PARA[i][1]))


ETH_C = (130, 140, 255); ETH_L = (190, 196, 255)
def eth_logo(cv, x, y, r, a=1.0, col=ETH_C, coll=ETH_L):
    """Ethereum diamond, r = half height"""
    if r < 2 or a <= 0: return
    w = r * .6
    cv.glow(x, y, r * 1.3, col, .22 * a)
    cv.poly([(x, y - r), (x + w, y + r * .08), (x, y + r * .36), (x - w, y + r * .08)], coll, a)
    cv.poly([(x, y - r), (x + w, y + r * .08), (x, y + r * .36)], col, a)
    cv.poly([(x, y + r * .48), (x + w, y + r * .2), (x, y + r), (x - w, y + r * .2)], coll, a)
    cv.poly([(x, y + r * .48), (x + w, y + r * .2), (x, y + r)], col, a)

def robot(cv, x, y, s, a=1.0, mood='smug', t=0.0, col=(150, 165, 190)):
    """little auction bot. s = scale (1 -> head 200 wide). mood: smug | happy | wow"""
    if s <= .02 or a <= 0: return
    cv.line([(x, y - 110 * s), (x, y - 160 * s)], col, 8 * s, a)
    cv.circle(x, y - 168 * s, 16 * s, DN if int(t * 4) % 2 else GOLD, a)
    cv.rect(x - 100 * s, y - 110 * s, x + 100 * s, y + 60 * s, col, a, r=34 * s)
    cv.rect(x - 80 * s, y - 85 * s, x + 80 * s, y + 20 * s, (24, 30, 44), a, r=22 * s)
    if mood == 'smug':   # sunglasses
        cv.rect(x - 70 * s, y - 60 * s, x - 8 * s, y - 28 * s, BLACK, a, r=10 * s)
        cv.rect(x + 8 * s, y - 60 * s, x + 70 * s, y - 28 * s, BLACK, a, r=10 * s)
        cv.line([(x - 8 * s, y - 50 * s), (x + 8 * s, y - 50 * s)], BLACK, 5 * s, a)
        cv.line([(x - 60 * s, y - 52 * s), (x - 44 * s, y - 40 * s)], (90, 100, 120), 3 * s, a)
    else:
        cv.circle(x - 38 * s, y - 45 * s, (20 if mood == 'wow' else 14) * s, (90, 230, 255), a)
        cv.circle(x + 38 * s, y - 45 * s, (20 if mood == 'wow' else 14) * s, (90, 230, 255), a)
    if mood == 'wow': cv.circle(x, y + 2 * s, 12 * s, (90, 230, 255), a)
    else: cv.line([(x - 34 * s + i * 6.8 * s, y - 6 * s + 9 * s * math.sin(i / 10 * math.pi)) for i in range(11)], (90, 230, 255), 5 * s, a)
    cv.rect(x - 70 * s, y + 70 * s, x + 70 * s, y + 190 * s, col, a, r=22 * s)
    cv.rect(x - 30 * s, y + 100 * s, x + 30 * s, y + 130 * s, (24, 30, 44), a, r=8 * s)

def paddle(cv, x, y, s, text, a=1.0, col=GOLD, fg=BG):
    """auction paddle: handle below a round sign"""
    if s <= .02 or a <= 0: return
    cv.rect(x - 12 * s, y + 60 * s, x + 12 * s, y + 230 * s, (150, 110, 70), a, r=6 * s)
    cv.circle(x, y, 120 * s, col, a); cv.ring(x, y, 120 * s, WHITE, 6 * s, a * .6)
    cv.text(x, y, text, 'black', 96, fg, a, anchor='cm', scale=max(s, .01))

def gavel(cv, x, y, s, ang, a=1.0):
    """gavel rotated by ang (rad) around its handle end at (x,y)"""
    if s <= .02 or a <= 0: return
    c, n = math.cos(ang), math.sin(ang)
    R = lambda u, v: (x + (u * c - v * n) * s, y + (u * n + v * c) * s)
    cv.poly([R(0, -10), R(200, -10), R(200, 10), R(0, 10)], (150, 105, 60), a)
    cv.poly([R(170, -70), R(250, -70), R(250, 70), R(170, 70)], (120, 80, 45), a)
    cv.poly([R(175, -70), R(245, -70), R(245, -56), R(175, -56)], GOLD, a)
    cv.poly([R(175, 56), R(245, 56), R(245, 70), R(175, 70)], GOLD, a)

def cta_layer(cv, t):
    """The channel end card (as in v12/v13): scene dims out, logo pops, red FOLLOW pill, tagline, fade to BG for the loop."""
    if CTA is None or t < CTA - .02: return
    cv.fill(BG, out3(seg(t, CTA, CTA + .3)))
    pl = back(seg(t, CTA + .1, CTA + .6), 1.8)
    cv.glow(W / 2, 820, 240, GOLD, .22 * clamp(pl))
    logo(cv, W / 2, 820, 1.0 * pl, clamp(pl * 2))
    pf = back(seg(t, CTA + .45, CTA + .85))
    if pf > 0:
        cv.rect(W / 2 - 350 * pf, 1140 - 56 * pf, W / 2 + 350 * pf, 1140 + 56 * pf, DN, 1, r=56 * pf)
        cv.text(W / 2, 1140, 'FOLLOW  ·  CHAIN SECRETS', 'black', 40, WHITE, 1, anchor='cm', scale=max(pf, .01))
    if TAGLINE: cv.text(W / 2, 1290, TAGLINE, 'semi', 44, MUTED, seg(t, (CTA2 or CTA + .85) - .05, (CTA2 or CTA + .85) + .35), anchor='cm')
    lp = seg(t, DUR - .6, DUR)
    if lp > 0: cv.fill(BG, clamp(lp * 2.2))

# ---------------- post FX ----------------
_GRAIN = [np.random.default_rng(s).normal(0, 1, (RH // 2, RW // 2)).astype(np.float32) for s in range(4)]
SCENES, IMPACTS, NAME = [], [], 'v'
TAGLINE = 'every chart hides a story'   # set to '' for stories without a chart
SHAKE, WHIP = 1.0, 1.0          # tone knobs for the automatic Shorts (serious = calmer camera)
def post(img, t):
    f = img.astype(np.float32)
    s = 1.0 + .012 * math.sin(t * .31) + .018 * ((t % 9) / 9)
    sx = sy = 0
    for b in IMPACTS:
        if b <= t < b + .8: s += .07 * SHAKE * (1 - out3(seg(t, b, b + .8)))
        if b <= t < b + .7:
            amp = 18 * SHAKE * (1 - seg(t, b, b + .7)) ** 1.6
            sx += amp * math.sin(t * 71); sy += amp * math.cos(t * 53)
    whip = 0.0
    for pb in [p[0] for p in PARA[1:]]:
        d = t - pb
        if -.16 < d < .16: whip = (1 - abs(d) / .16) * (1 if d < 0 else -1) * WHIP
    M = cv2.getRotationMatrix2D((RW / 2, RH / 2), 0, s)
    M[0, 2] += (6 * math.sin(t * .23) + sx) * K + whip * 260 * K
    M[1, 2] += (8 * math.cos(t * .19) + sy) * K
    f = cv2.warpAffine(f, M, (RW, RH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if abs(whip) > .02:
        k = int(abs(whip) * 90 * K) | 1
        f = cv2.blur(f, (k, 1))
    g = 0.0
    for b in IMPACTS:
        if b <= t < b + .35: g = max(g, 1 - seg(t, b, b + .35))
    if g > .02:
        dx = int(14 * g * K)
        f[..., 0] = np.roll(f[..., 0], dx, 1); f[..., 2] = np.roll(f[..., 2], -dx, 1)
        if g > .5:
            for k in range(3):
                y0 = int((math.sin(t * 97 + k) * .5 + .5) * (RH - 60)); h = int(20 * K)
                f[y0:y0 + h] = np.roll(f[y0:y0 + h], int(40 * g * K * (1 if k % 2 else -1)), 1)
    gr = cv2.resize(_GRAIN[int(t * 24) % 4], (RW, RH), interpolation=cv2.INTER_NEAREST)
    f += gr[..., None] * 2.2
    return np.clip(f, 0, 255).astype(np.uint8)

_VIG = None
def frame(t):
    global _VIG
    cv = Canvas(); background(cv)
    i = 0
    while i + 1 < len(PARA) and t >= PARA[i + 1][0]: i += 1
    SCENES[i](cv, t)
    cta_layer(cv, t)
    caption_layer(cv, t)
    progress_bar(cv, t, DUR)
    if _VIG is None:
        yy, xx = np.mgrid[0:RH, 0:RW].astype(np.float32)
        d = np.sqrt(((xx - RW / 2) / RW) ** 2 + ((yy - RH / 2) / RH) ** 2)
        _VIG = np.clip(1 - (d - .35) * 1.1, .62, 1)[..., None].astype(np.float32)
    cv.a *= _VIG
    return post(cv.image(), t)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'stills':
        from PIL import Image
        ims = [Image.fromarray(frame(float(s))).resize((360, 640), Image.LANCZOS) for s in sys.argv[2:]]
        cols = 6
        sheet = Image.new('RGB', (360 * min(cols, len(ims)), 640 * ((len(ims) + cols - 1) // cols)))
        for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 360, (i // cols) * 640))
        sheet.save(f'{HERE}/{NAME}_sheet.png'); sys.exit()
    if len(sys.argv) > 1 and sys.argv[1] == 'part':
        a, b = int(sys.argv[2]), int(sys.argv[3])
        encode(frame, DUR, f'{HERE}/{NAME}_part_{a}.mp4', crf=16, start=a, end=b)
        print('part done', a, b); sys.exit()
    encode(frame, DUR, f'{HERE}/{NAME}_silent.mp4', crf=16)
