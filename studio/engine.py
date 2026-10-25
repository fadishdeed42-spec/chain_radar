"""Chart-story engine: antialiased 1080x1920 frames for vertical Shorts.
Shapes via OpenCV (LINE_AA, sub-pixel), text via PIL/raqm with Inter."""
import math, subprocess, functools
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

import os as _os
W, H = 1080, 1920                         # logical canvas (all scene coordinates)
K = float(_os.environ.get('CS_SCALE', '1'))  # render scale: 1 -> 1080x1920, 4/3 -> 1440x2560
RW, RH = int(round(W * K)), int(round(H * K))
SH = 4                      # sub-pixel bits for cv2
S = 1 << SH

# ---------- palette ----------
BG = (13, 17, 26); BG2 = (19, 24, 36); PANEL = (22, 27, 40); GRID = (34, 40, 56)
AXIS = (118, 128, 148); TXT = (238, 241, 247); MUTED = (150, 158, 176)
UP = (38, 194, 160); DN = (246, 70, 93); GOLD = (255, 196, 46); BLUE = (64, 120, 255)
PURPLE = (150, 110, 255); WHITE = (255, 255, 255); BLACK = (0, 0, 0)

_FD = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'fonts')   # bundled Inter (OFL) so GitHub renders identically
FONTS = {
    'black': f'{_FD}/InterDisplay-Black.otf',
    'xbold': f'{_FD}/InterDisplay-ExtraBold.otf',
    'bold': f'{_FD}/Inter-Bold.otf',
    'semi': f'{_FD}/Inter-SemiBold.otf',
    'med': f'{_FD}/Inter-Medium.otf',
    'reg': f'{_FD}/Inter-Regular.otf',
}

@functools.lru_cache(maxsize=None)
def font(kind, size):
    return ImageFont.truetype(FONTS[kind], size, layout_engine=ImageFont.Layout.RAQM)

# ---------- easing ----------
def clamp(x, a=0., b=1.): return a if x < a else b if x > b else x
def seg(t, a, b): return clamp((t - a) / (b - a))
def smooth(x): x = clamp(x); return x * x * x * (x * (6 * x - 15) + 10)       # smootherstep
def out3(x): x = clamp(x); return 1 - (1 - x) ** 3
def out5(x): x = clamp(x); return 1 - (1 - x) ** 5
def back(x, s=1.7):
    x = clamp(x); x -= 1; return x * x * ((s + 1) * x + s) + 1
def lerp(a, b, t): return a + (b - a) * t

def keyframes(t, keys, fn=smooth):
    """keys: [(time, value_tuple), ...] -> interpolated tuple"""
    if t <= keys[0][0]: return keys[0][1]
    for (ta, va), (tb, vb) in zip(keys, keys[1:]):
        if t <= tb:
            s = fn(seg(t, ta, tb)); return tuple(lerp(a, b, s) for a, b in zip(va, vb))
    return keys[-1][1]

# ---------- text patches (cached, white glyph alpha) ----------
@functools.lru_cache(maxsize=4096)
def text_mask(text, kind, size, tnum=False, track=0):
    f = font(kind, size)
    feats = ['tnum'] if tnum else None
    bbox = f.getbbox(text, features=feats)
    asc, desc = f.getmetrics()
    w = int(math.ceil(f.getlength(text, features=feats))) + 8 + max(0, track * len(text))
    h = asc + desc + 8
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    if track:
        x = 4
        for ch in text:
            d.text((x, 4), ch, font=f, fill=255, features=feats); x += f.getlength(ch, features=feats) + track
    else:
        d.text((4, 4), text, font=f, fill=255, features=feats)
    return np.asarray(im, dtype=np.float32) / 255.0, asc

def text_size(text, kind, size, tnum=False, track=0):
    m, asc = text_mask(text, kind, size, tnum, track)
    return m.shape[1] - 8, m.shape[0] - 8

@functools.lru_cache(maxsize=512)
def blur_mask(r, sigma):
    s = int(r * 2 + sigma * 6)
    m = np.zeros((s, s), np.float32)
    cv2.circle(m, (s // 2, s // 2), int(r), 1.0, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(m, (0, 0), sigma)

class Canvas:
    def __init__(self, bg=BG):
        self.a = np.empty((RH, RW, 3), np.float32)
        self.a[:] = bg

    # --- low level blend of a [0..1] mask with a color ---
    def blend_mask(self, mask, x, y, color, alpha=1.0):
        if alpha <= 0.003: return
        h, w = mask.shape
        x0, y0 = int(round(x)), int(round(y))
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(RW, x0 + w), min(RH, y0 + h)
        if xa >= xb or ya >= yb: return
        m = mask[ya - y0:yb - y0, xa - x0:xb - x0, None] * alpha
        roi = self.a[ya:yb, xa:xb]
        roi += (np.array(color, np.float32) - roi) * m

    def _shape(self, draw_fn, bbox, color, alpha):
        x0, y0, x1, y1 = [int(v) for v in (bbox[0] - 3, bbox[1] - 3, bbox[2] + 4, bbox[3] + 4)]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(RW, x1), min(RH, y1)
        if x0 >= x1 or y0 >= y1: return
        m = np.zeros((y1 - y0, x1 - x0), np.float32)
        draw_fn(m, x0, y0)
        self.blend_mask(m, x0, y0, color, alpha)

    def poly(self, pts, color, alpha=1.0):
        pts = np.asarray(pts, np.float64) * K
        bb = (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max())
        def f(m, ox, oy):
            p = np.round((pts - (ox, oy)) * S).astype(np.int32)
            cv2.fillPoly(m, [p], 1.0, cv2.LINE_AA, SH)
        self._shape(f, bb, color, alpha)

    def rect(self, x0, y0, x1, y1, color, alpha=1.0, r=0):
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0
        if r <= 0:
            self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color, alpha); return
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        pts = []
        for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
            for k in range(9):
                a = math.radians(a0 + k * 90 / 8); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.poly(pts, color, alpha)

    def line(self, pts, color, width=2, alpha=1.0):
        pts = np.asarray(pts, np.float64) * K
        width = width * K
        if len(pts) < 2: return
        bb = (pts[:, 0].min() - width, pts[:, 1].min() - width, pts[:, 0].max() + width, pts[:, 1].max() + width)
        def f(m, ox, oy):
            p = np.round((pts - (ox, oy)) * S).astype(np.int32)
            cv2.polylines(m, [p], False, 1.0, max(1, int(round(width))), cv2.LINE_AA, SH)
        self._shape(f, bb, color, alpha)

    def dashed(self, x0, y, x1, color, alpha=1.0, dash=12, gap=9, width=2):
        x = x0
        while x < x1:
            self.line([(x, y), (min(x + dash, x1), y)], color, width, alpha); x += dash + gap

    def circle(self, x, y, r, color, alpha=1.0):
        x, y, r = x * K, y * K, r * K
        def f(m, ox, oy):
            cv2.circle(m, (int(round((x - ox) * S)), int(round((y - oy) * S))), int(round(r * S)), 1.0, -1, cv2.LINE_AA, SH)
        self._shape(f, (x - r, y - r, x + r, y + r), color, alpha)

    def ring(self, x, y, r, color, width=3, alpha=1.0):
        x, y, r, width = x * K, y * K, r * K, width * K
        def f(m, ox, oy):
            cv2.circle(m, (int(round((x - ox) * S)), int(round((y - oy) * S))), int(round(r * S)), 1.0, max(1, int(width)), cv2.LINE_AA, SH)
        self._shape(f, (x - r - width, y - r - width, x + r + width, y + r + width), color, alpha)

    def glow(self, x, y, r, color, alpha=0.5, sigma=None):
        sigma = (sigma or r * .6) * K
        x, y, r = x * K, y * K, r * K
        m = blur_mask(int(r), round(sigma, 1))
        self.blend_mask(m, x - m.shape[1] / 2, y - m.shape[0] / 2, color, alpha)

    def fill(self, color, alpha=1.0):
        if alpha <= 0: return
        self.a += (np.array(color, np.float32) - self.a) * alpha

    # --- text ---
    def text(self, x, y, s, kind='bold', size=40, color=TXT, alpha=1.0, anchor='lt', scale=1.0,
             tnum=False, track=0, shadow=0):
        """anchor: horizontal l/c/r + vertical t/m/b (relative to glyph box)"""
        if alpha <= 0.003 or not s: return
        x, y = x * K, y * K
        m, asc = text_mask(s, kind, max(1, int(round(size * K))), tnum, int(round(track * K)))
        if scale != 1.0:
            if scale <= 0.02: return
            m = cv2.resize(m, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR if scale > 1 else cv2.INTER_AREA)
        h, w = m.shape
        ax = {'l': 0, 'c': .5, 'r': 1}[anchor[0]]; ay = {'t': 0, 'm': .5, 'b': 1}[anchor[1]]
        px, py = x - 4 * scale - (w - 8 * scale) * ax, y - 4 * scale - (h - 8 * scale) * ay
        if shadow:
            sm = cv2.GaussianBlur(m, (0, 0), shadow * K)
            self.blend_mask(sm, px, py + shadow * K * .6, BLACK, alpha * .85)
        self.blend_mask(m, px, py, color, alpha)
        return (w - 8 * scale) / K, (h - 8 * scale) / K

    def image(self):
        return np.clip(self.a + _dither(), 0, 255).astype(np.uint8)

_DITH = None
def _dither():
    global _DITH
    if _DITH is None:
        rng = np.random.default_rng(7)
        _DITH = (rng.random((RH, RW, 1), dtype=np.float32) + rng.random((RH, RW, 1), dtype=np.float32) - 1.0) * 1.6
    return _DITH

# ---------- shared visual pieces ----------
_vig = None
def background(cv):
    global _vig
    if _vig is None:
        yy, xx = np.mgrid[0:RH, 0:RW].astype(np.float32)
        d = np.sqrt(((xx - RW / 2) / RW) ** 2 + ((yy - RH * .45) / RH) ** 2)
        g = np.clip(1 - d * 1.1, 0, 1)[..., None]
        _vig = (np.array(BG, np.float32) * (1 - g) + np.array(BG2, np.float32) * g)
    cv.a[:] = _vig

def nice_step(rng, n=5):
    raw = rng / n; mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw: return m * mag

def fmt_price(p):
    if p >= 1000: return f'{p:,.0f}'
    if p >= 10: return f'{p:,.1f}'
    if p >= 1: return f'{p:,.2f}'
    if p >= 0.01: return f'{p:.3f}'
    return (f'{p:.8f}').rstrip('0')

class Chart:
    """Candle chart in a screen box with a camera (x0,x1,ymin,ymax)."""
    def __init__(self, data, box=(30, 360, 870, 1180), vol_box=None, log=False):
        self.d = data; self.box = box; self.vb = vol_box; self.log = log
        self.cam = (0, 10, 0, 1)

    def fy(self, p): return math.log10(max(p, 1e-9)) if self.log else p
    def X(self, i):
        x0, x1 = self.cam[0], self.cam[1]; bx0, _, bx1, _ = self.box
        return bx0 + (i - x0) / (x1 - x0) * (bx1 - bx0)
    def Y(self, p):
        _, by0, _, by1 = self.box; lo, hi = self.fy(self.cam[2]), self.fy(self.cam[3])
        return by1 - (self.fy(p) - lo) / (hi - lo) * (by1 - by0)
    def cw(self):
        return 0.66 * (self.box[2] - self.box[0]) / (self.cam[1] - self.cam[0])

    def ohlc(self, k, u=1.0):
        d = self.d; o, h, l, c = d['o'][k], d['h'][k], d['l'][k], d['c'][k]
        if u >= 1: return o, h, l, c
        pts = [o, h, l, c] if c < o else [o, l, h, c]
        u = clamp(u) * 3; i = min(int(u), 2); p = lerp(pts[i], pts[i + 1], smooth(u - i))
        seen = pts[:i + 1] + [p]
        return o, max(seen), min(seen), p

    def grid(self, cv, alpha=1.0):
        bx0, by0, bx1, by1 = self.box
        if self.log:
            lo, hi = self.cam[2], self.cam[3]
            levels = []
            e = math.floor(math.log10(lo))
            while 10 ** e <= hi * 1.01:
                for m in (1, 3) if hi / lo > 300 else (1, 2, 5):
                    v = m * 10 ** e
                    if lo <= v <= hi: levels.append(v)
                e += 1
        else:
            st = nice_step(self.cam[3] - self.cam[2])
            v = math.ceil(self.cam[2] / st) * st; levels = []
            while v < self.cam[3]: levels.append(v); v += st
        for v in levels:
            y = self.Y(v)
            if by0 - 2 <= y <= by1 + 2:
                cv.line([(bx0, y), (bx1, y)], GRID, 2, alpha * .9)
                if self.log: lab = f'{v/1000:g}K' if v >= 1000 else (f'{v:g}' if v >= 0.001 else fmt_price(v))
                else: lab = (f'{v/1000:,.0f}K' if v % 1000 == 0 and v >= 10000 else fmt_price(v))
                cv.text(bx1 + 16, y, lab, 'med', 26, AXIS, alpha, anchor='lm', tnum=True)

    def candles(self, cv, last, u=1.0, first=0, dim=None, grow_new=True, alpha=1.0):
        """draw candles first..last, last forming with progress u. dim: set of indices kept bright."""
        bx0, by0, bx1, by1 = self.box
        cw = self.cw(); k0 = max(first, int(self.cam[0]) - 1)
        vols = None
        if self.vb and 'v' in self.d:
            lo = max(0, int(self.cam[0])); hiK = min(last, int(self.cam[1]) + 1)
            vmax = max(self.d['v'][lo:hiK + 1] or [1])
        for k in range(k0, min(last, len(self.d['o']) - 1) + 1):
            x = self.X(k)
            if x < bx0 - cw or x > bx1 + cw: continue
            o, h, l, c = self.ohlc(k, u if k == last else 1.0)
            col = UP if c >= o else DN
            a = alpha * (1.0 if dim is None or k in dim else .28)
            ww = max(1.5, min(5, cw * .14))
            yh, yl = self.Y(h), self.Y(l)
            yh, yl = max(by0 - 40, yh), min(by1 + 40, yl)
            cv.line([(x, yh), (x, yl)], col, ww, a)
            yt, yb = self.Y(max(o, c)), self.Y(min(o, c))
            if yb - yt < 2: yb = yt + 2
            cv.rect(x - cw / 2, yt, x + cw / 2, yb, col, a, r=min(3, cw * .12))
            if self.vb:
                vx0, vy0, vx1, vy1 = self.vb
                vv = self.d['v'][k] * (u if k == last else 1)
                cv.rect(x - cw / 2, vy1 - (vy1 - vy0) * vv / vmax, x + cw / 2, vy1, col, a * .55, r=2)

    def price_tag(self, cv, price, col, alpha=1.0):
        bx0, by0, bx1, by1 = self.box
        y = self.Y(price)
        if not (by0 - 10 <= y <= by1 + 10): return
        cv.dashed(bx0, y, bx1, col, alpha * .8)
        cv.rect(bx1 + 6, y - 22, W - 8, y + 22, col, alpha, r=8)
        cv.text(bx1 + 16, y, fmt_price(price), 'bold', 27, WHITE, alpha, anchor='lm', tnum=True)

def callout(cv, x0, y0, x1, y1, text, col, p, size=40, kind='bold', side=None):
    """dot at (x0,y0) -> leader -> pill label centered vertically at y1 starting/ending at x1."""
    if p <= 0: return
    a = out3(p)
    cv.glow(x0, y0, 22, col, .45 * a)
    cv.circle(x0, y0, 9 * a, col, 1)
    ex, ey = lerp(x0, x1, out3(seg(p, 0, .6))), lerp(y0, y1, out3(seg(p, 0, .6)))
    cv.line([(x0, y0), (ex, ey)], col, 4, a)
    q = back(seg(p, .45, 1))
    if q > 0:
        tw, th = text_size(text, kind, size)
        w, h = tw + 44, th + 34
        left = x1 < x0 if side is None else side == 'left'
        bx = x1 - w if left else x1
        bx = clamp(bx, 16, W - 16 - w)
        cx, cy = bx + w / 2, y1
        cv.rect(cx - w / 2 * q, cy - h / 2 * q, cx + w / 2 * q, cy + h / 2 * q, col, 1, r=h / 2 * q)
        cv.text(cx, cy, text, kind, size, WHITE, clamp(q), anchor='cm', scale=max(q, .01))

def pop_words(cv, t, t0, text, y, size=58, kind='black', color=TXT, hl=None, per=0.07, alpha=1.0,
              stroke_bg=True, max_w=980, line_gap=1.18):
    """word-by-word pop caption. hl: {word: color}. Wraps to lines."""
    if t < t0 or alpha <= 0: return
    words = text.split(' ')
    sp = text_size(' ', kind, size)[0] + size * .1
    lines, cur, cw_ = [], [], 0
    for wd in words:
        ww = text_size(wd, kind, size)[0]
        if cur and cw_ + sp + ww > max_w: lines.append(cur); cur, cw_ = [], 0
        cur.append((wd, ww)); cw_ += (sp if len(cur) > 1 else 0) + ww
    if cur: lines.append(cur)
    i = 0
    for li, ln in enumerate(lines):
        total = sum(w for _, w in ln) + sp * (len(ln) - 1)
        x = (W - total) / 2; yy = y + li * size * line_gap
        for wd, ww in ln:
            p = seg(t, t0 + i * per, t0 + i * per + .28)
            if p > 0:
                s = lerp(.55, 1, back(p, 2.2))
                col = (hl or {}).get(wd.strip('.,!?:'), color)
                cv.text(x + ww / 2, yy, wd, kind, size, col, alpha * clamp(p * 2), anchor='cm', scale=s, shadow=6)
            x += ww + sp; i += 1

def header(cv, series, ep, symbol, sub, price, pcol, date, tf=None, alpha=1.0, badge=GOLD, badge_txt=BG):
    cv.rect(0, 0, W, 300, PANEL, alpha * .96)
    cv.line([(0, 300), (W, 300)], GRID, 2, alpha)
    # series badge
    tw, _ = text_size(series, 'black', 30, track=3)
    cv.rect(36, 52, 36 + tw + 40, 100, badge, alpha, r=12)
    cv.text(56, 76, series, 'black', 30, badge_txt, alpha, anchor='lm', track=3)
    cv.text(36 + tw + 58, 76, f'#{ep}', 'xbold', 34, badge, alpha, anchor='lm')
    sw, _ = text_size(symbol, 'xbold', 50)
    cv.text(36, 150, symbol, 'xbold', 50, TXT, alpha, anchor='lt')
    if tf:
        tw2, _ = text_size(tf, 'bold', 26)
        x = 36 + sw + 18
        cv.rect(x, 152, x + tw2 + 28, 196, BLUE, alpha, r=10)
        cv.text(x + 14 + tw2 / 2, 174, tf, 'bold', 26, WHITE, alpha, anchor='cm')
    cv.text(36, 214, sub, 'med', 28, MUTED, alpha, anchor='lt')
    cv.text(W - 40, 150, fmt_price(price), 'xbold', 66, pcol, alpha, anchor='rt', tnum=True)
    cv.text(W - 40, 236, date, 'semi', 28, MUTED, alpha, anchor='rt', tnum=True)

def progress_bar(cv, t, dur):
    cv.rect(0, 0, W * clamp(t / dur), 8, GOLD, .95)

def footer(cv, text='Not financial advice · Data: Bitstamp BTC/USD'):
    cv.text(W / 2, H - 70, text, 'med', 24, (88, 96, 116), 1, anchor='cm')

def encode(frame_fn, dur, out, fps=60, crf=15, start=0, end=None):
    """render frames [start, end) (frame indices) to out"""
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                          '-s', f'{RW}x{RH}', '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-profile:v', 'high',
                          '-pix_fmt', 'yuv420p', '-crf', str(crf), '-preset', 'slow', '-tune', 'animation',
                          '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    n = int(round(dur * fps))
    for i in range(start, n if end is None else min(end, n)):
        p.stdin.write(frame_fn(i / fps).tobytes())
    p.stdin.close(); p.wait()
