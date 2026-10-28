"""Chain Secrets chart v2: a chart is only made when the move is big enough that people react, and it is drawn clean.

worth_it(): the rule. 24h or 7d move of 10% or more, or a month/2-month move of +100% (or -50%, the same size in the other direction).
render(): hero number, one clean line/candle chart with the start, end and key moment marked, honest source line. 1080x1350, Pillow only.
Pure functions (no network): radar.py fetches the candles.
"""
import math
from datetime import datetime, timezone
from PIL import Image, ImageDraw
import card
from card import F, W, H, BLACK, XB, BOLD, SEMI, MED, WHITE, MUT, DIM, GRN, RED, GOLD, PANEL, LINE, fmt

# (key, seconds, label, up threshold, down threshold)
WINDOWS = [('24h', 86400, 'in 24 hours', .10, -.10), ('7d', 7 * 86400, 'in 7 days', .10, -.10),
           ('30d', 30 * 86400, 'in 30 days', 1.0, -.50), ('60d', 60 * 86400, 'in 60 days', 1.0, -.50)]


def move(rows, secs):
    """pct change over the last `secs` of candles (open of the first candle in the window -> last close), and the rows used"""
    if not rows:
        return None, []
    t_end = rows[-1][0]
    win = [r for r in rows if r[0] >= t_end - secs * 1000 + 1]
    if len(win) < 8:
        return None, []
    return win[-1][4] / win[0][1] - 1, win


def worth_it(rows_by_window):
    """rows_by_window = {'24h': candles, '7d': ..., '30d': ..., '60d': ...} (any may be missing).
    Returns the most remarkable window as {'key','label','move','rows'} or None when nothing is big enough to react to."""
    best = None
    for key, secs, label, up, dn in WINDOWS:
        mv, win = move(rows_by_window.get(key) or [], secs)
        if mv is None:
            continue
        ratio = mv / up if mv >= 0 else mv / dn                       # how many times over the threshold
        if ratio >= 1 and (best is None or ratio > best['ratio']):
            best = {'key': key, 'label': label, 'move': mv, 'rows': win, 'ratio': ratio}
    return best


def _ss(img_size, scale=3):
    return Image.new('RGBA', (img_size[0] * scale, img_size[1] * scale), (0, 0, 0, 0))


def span_label(secs):
    h = secs / 3600
    return 'in 1 hour' if h <= 1.5 else f'in {h:.0f} hours' if h <= 36 else f'in {h / 24:.0f} days'


def render(title_name, sym, rows, label, source, tag='MOVER', event_ms=None, event_label='', headline=None, hero=None):
    """rows: [(t_ms, o, h, l, c, v)]. label: 'in 24 hours'. event_ms: moment to mark (optional). Returns (png bytes, pct move)."""
    first, last = rows[0][1], rows[-1][4]; mv = last / first - 1
    if hero:                                                           # the move the story is about (e.g. since the news), not the whole window
        mv, label = hero
    up = mv >= 0
    acc = GRN if up else RED
    im = card.canvas(acc, strength=.16); d = card.header(im, tag)
    # hero number
    pct = f'{mv * 100:+,.0f}%' if abs(mv) >= 1 else f'{mv * 100:+.1f}%'
    d.text((56, 150), pct, font=F(BLACK, 190), fill=acc)
    d.text((60, 352), f'{title_name} ({sym}) {label}', font=F(BOLD, 40), fill=WHITE)
    if headline:
        card.headline(d, headline, 412, sizes=(40, 36, 32), maxlines=2, gold_nums=False, color=MUT)
    # chart panel
    top, bot = 470, 1190
    d.rounded_rectangle([36, top, W - 36, bot], radius=28, fill=PANEL, outline=LINE, width=2)
    cx0, cx1 = 76, W - 190; cy0, cy1 = top + 60, bot - 70
    hi = max(r[2] for r in rows); lo = min(r[3] for r in rows); pad = (hi - lo) * .10 or hi * .02; hi += pad; lo -= pad
    Y = lambda p: cy1 - (p - lo) / (hi - lo) * (cy1 - cy0)
    n = len(rows); X = lambda i: cx0 + (cx1 - cx0) * i / max(1, n - 1)
    for i in range(5):                                                 # four quiet price guides, labelled once
        p = lo + (hi - lo) * i / 4; yy = Y(p)
        d.line([cx0, yy, cx1, yy], fill=(26, 31, 43), width=1)
        d.text((cx1 + 18, yy), fmt(p), font=F(MED, 18), fill=DIM, anchor='lm')
    # line + soft area, drawn 3x for smooth edges
    S = 3; lay = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    pts = [(X(i) * S, Y(r[4]) * S) for i, r in enumerate(rows)]
    if n <= 120:                                                       # fewer candles: show them, they ARE the data
        bw = max(3, (cx1 - cx0) / n * .62)
        for i, (t, o, h, l, c, v) in enumerate(rows):
            col = GRN if c >= o else RED
            ld.line([X(i) * S, Y(h) * S, X(i) * S, Y(l) * S], fill=col + (255,), width=int(2 * S))
            y0, y1 = sorted((Y(o), Y(c)))
            ld.rectangle([(X(i) - bw / 2) * S, y0 * S, (X(i) + bw / 2) * S, max(y1, y0 + 2) * S], fill=col + (255,))
    else:
        ld.polygon(pts + [(pts[-1][0], cy1 * S), (pts[0][0], cy1 * S)], fill=acc + (46,))
        ld.line(pts, fill=acc + (255,), width=int(5 * S), joint='curve')
    lay = lay.resize((W, H), Image.LANCZOS); im.paste(lay, (0, 0), lay); d = ImageDraw.Draw(im)
    # start and end markers
    y0p, y1p = Y(first), Y(last)
    d.ellipse([X(0) - 9, y0p - 9, X(0) + 9, y0p + 9], fill=WHITE, outline=(14, 17, 25), width=3)
    d.rounded_rectangle([cx0, y0p + (16 if y0p < (cy0 + cy1) / 2 else -50), cx0 + 18 + d.textlength(fmt(first), font=F(BLACK, 22)), y0p + (46 if y0p < (cy0 + cy1) / 2 else -16)], radius=8, fill=(30, 36, 50))
    d.text((cx0 + 9, y0p + (31 if y0p < (cy0 + cy1) / 2 else -33)), fmt(first), font=F(BLACK, 22), fill=WHITE, anchor='lm')
    for xx in range(int(cx0), int(cx1), 12):
        d.line([xx, y1p, xx + 5, y1p], fill=tuple(int(c * .7) for c in acc), width=2)
    d.ellipse([X(n - 1) - 10, y1p - 10, X(n - 1) + 10, y1p + 10], fill=acc, outline=(14, 17, 25), width=3)
    d.rounded_rectangle([cx1 + 8, y1p - 19, W - 44, y1p + 19], radius=8, fill=acc)
    d.text(((cx1 + 8 + W - 44) / 2, y1p), fmt(last), font=F(BLACK, 20), fill=(8, 10, 12), anchor='mm')
    # key moment
    if event_ms:
        e = min(range(n), key=lambda i: abs(rows[i][0] - event_ms))
        xe = X(e)
        for yy in range(int(cy0 - 18), int(cy1), 12):
            d.line([xe, yy, xe, yy + 6], fill=GOLD, width=2)
        lab = event_label or datetime.fromtimestamp(rows[e][0] / 1000, timezone.utc).strftime('%b %d, %Y')
        lw = d.textlength(lab, font=F(BLACK, 20)) + 26; lx = min(max(xe - lw / 2, cx0), cx1 - lw)
        d.rounded_rectangle([lx, cy0 - 56, lx + lw, cy0 - 22], radius=10, fill=GOLD)
        d.text((lx + lw / 2, cy0 - 39), lab, font=F(BLACK, 20), fill=(20, 16, 6), anchor='mm')
    # dates: 4 labels only
    multi = (rows[-1][0] - rows[0][0]) >= 2 * 86400000
    for i in sorted({0, n // 3, 2 * n // 3, n - 1}):
        dt = datetime.fromtimestamp(rows[i][0] / 1000, timezone.utc)
        d.text((min(max(X(i), cx0 + 30), cx1 - 20), bot - 30), dt.strftime('%b %d' if multi else '%H:%M UTC'), font=F(MED, 19), fill=DIM, anchor='mm')
    d.text((56, 1302), 'Every chart hides a story', font=F(MED, 20), fill=MUT, anchor='lm')
    d.text((W - 56, 1302), f'Data: {source} · real candles', font=F(MED, 17), fill=DIM, anchor='rm')
    return card.png(im), mv
