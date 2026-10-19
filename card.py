"""Chain Secrets post images (1080x1350): real candlestick chart cards and headline cards, drawn with Pillow."""
import io, os, re, math
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1350
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
_f = {}


def F(name, size):
    k = (name, size)
    if k not in _f:
        _f[k] = ImageFont.truetype(os.path.join(FD, name + '.otf'), size)
    return _f[k]


BLACK, BOLD, SEMI, MED, REG = 'InterDisplay-Black', 'InterDisplay-Bold', 'Inter-SemiBold', 'Inter-Medium', 'Inter-Regular'
BG1, BG2 = (14, 17, 24), (6, 7, 10)
PANEL, LINE = (16, 20, 29), (32, 38, 52)
WHITE, MUT, DIM = (240, 242, 247), (138, 147, 166), (78, 86, 104)
GOLD, RED, GRN = (226, 178, 72), (239, 68, 80), (38, 199, 160)
NUM = re.compile(r'^[\$€£]?[\d][\d,.]*[%kKmMbB]?\+?$|^(million|billion|trillion|record|%)$', re.I)


def _bg(accent):
    from PIL import ImageChops
    grad = Image.linear_gradient('L').resize((W, H))
    im = Image.composite(Image.new('RGB', (W, H), BG2), Image.new('RGB', (W, H), BG1), grad)
    glow = Image.new('RGB', (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W * 0.1, H * 0.36, W * 1.1, H * 0.98], fill=tuple(int(v * 0.20) for v in accent))
    return ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(170)))


def _header(d, tag, tag_col, when=None):
    d.ellipse([60, 52, 112, 104], outline=GOLD, width=4)
    d.text((86, 78), 'CS', font=F(BLACK, 22), fill=GOLD, anchor='mm')
    d.text((128, 58), 'CHAIN SECRETS', font=F(BLACK, 28), fill=WHITE)
    d.text((129, 98), '@thechainsecrets', font=F(MED, 17), fill=MUT)
    tw = d.textlength(tag, font=F(BLACK, 22))
    x1 = W - 60; x0 = x1 - tw - 44
    d.rounded_rectangle([x0, 56, x1, 98], radius=21, fill=tag_col)
    d.text(((x0 + x1) / 2, 77), tag, font=F(BLACK, 22), fill=(255, 255, 255), anchor='mm')
    when = when or datetime.now(timezone.utc)
    d.text((x1, 116), when.strftime('%b %d, %Y · %H:%M UTC').upper(), font=F(SEMI, 16), fill=DIM, anchor='ra')


def _headline(d, text, y, maxw=960, sizes=(68, 60, 54, 48), maxlines=3):
    words = text.split()
    for s in sizes:
        f = F(BLACK, s); lines, cur = [], []
        for w in words:
            if d.textlength(' '.join(cur + [w]), font=f) <= maxw:
                cur.append(w)
            else:
                lines.append(cur); cur = [w]
        lines.append(cur)
        if len(lines) <= maxlines:
            break
    lines = lines[:maxlines]
    for ln in lines:
        x = 60
        for w in ln:
            col = GOLD if NUM.match(w.strip(',.:;!?()"\'')) else WHITE
            d.text((x, y), w, font=f, fill=col)
            x += d.textlength(w + ' ', font=f)
        y += int(s * 1.12)
    return y


def _fmt(v):
    if v >= 1000:
        return f'${v:,.0f}'
    if v >= 1:
        return f'${v:,.2f}'
    return f'${v:.4g}'


def _png(im):
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()


def chart_card(title, coin, rows, tf_label, tag='BREAKING', tag_col=RED, source='CoinGecko', note=None):
    """rows: list of (t_ms, o, h, l, c, v_or_None), oldest first."""
    first, last = rows[0][1], rows[-1][4]
    ch = (last / first - 1) * 100
    up = ch >= 0
    acc = GRN if up else RED
    im = _bg(acc)
    d = ImageDraw.Draw(im)
    _header(d, tag, tag_col)
    y = _headline(d, title, 150)
    # coin line
    y += 8
    d.text((60, y), f'{coin["name"]} ({coin["sym"]})', font=F(BOLD, 34), fill=WHITE)
    px = 60 + d.textlength(f'{coin["name"]} ({coin["sym"]})  ', font=F(BOLD, 34))
    d.text((px, y), _fmt(last), font=F(BOLD, 34), fill=WHITE)
    px += d.textlength(_fmt(last) + '  ', font=F(BOLD, 34))
    chip = f'{"▲" if up else "▼"} {abs(ch):.1f}%'
    cw = d.textlength(chip, font=F(BLACK, 26)) + 28
    d.rounded_rectangle([px, y + 2, px + cw, y + 42], radius=12, fill=tuple(int(v * 0.25) for v in acc), outline=acc, width=2)
    d.text((px + cw / 2, y + 22), chip, font=F(BLACK, 26), fill=acc, anchor='mm')
    d.text((px + cw + 14, y + 22), tf_label, font=F(MED, 20), fill=MUT, anchor='lm')
    # panel
    top = max(y + 70, 470); bot = 1150
    d.rounded_rectangle([40, top, W - 40, bot], radius=28, fill=PANEL, outline=LINE, width=2)
    cx0, cx1 = 70, W - 150
    has_v = any(r[5] for r in rows)
    cy0, cy1 = top + 40, bot - (130 if has_v else 70)
    hi = max(r[2] for r in rows); lo = min(r[3] for r in rows)
    pad = (hi - lo) * 0.08 or hi * 0.01
    hi += pad; lo -= pad
    Y = lambda p: cy1 - (p - lo) / (hi - lo) * (cy1 - cy0)
    n = len(rows); step = (cx1 - cx0) / n; bw = max(3, step * 0.62)
    for i in range(5):                                     # grid + price labels
        p = lo + (hi - lo) * i / 4; yy = Y(p)
        d.line([cx0, yy, cx1, yy], fill=(26, 31, 43), width=1)
        d.text((cx1 + 14, yy), _fmt(p), font=F(MED, 18), fill=DIM, anchor='lm')
    vmax = max((r[5] or 0) for r in rows) or 1
    big = max(range(n), key=lambda i: abs(rows[i][4] - rows[i][1]) / rows[i][1])
    for i, (t, o, h, l, c, v) in enumerate(rows):
        x = cx0 + step * (i + 0.5); col = GRN if c >= o else RED
        d.line([x, Y(h), x, Y(l)], fill=col, width=2 if bw > 5 else 1)
        y0, y1 = sorted((Y(o), Y(c)))
        d.rectangle([x - bw / 2, y0, x + bw / 2, max(y1, y0 + 2)], fill=col)
        if has_v and v:
            vh = (v / vmax) * 70
            d.rectangle([x - bw / 2, bot - 40 - vh, x + bw / 2, bot - 40], fill=tuple(int(cc * 0.45) for cc in col))
    # last price line + pill
    ly = Y(last)
    for xx in range(cx0, int(cx1), 14):
        d.line([xx, ly, xx + 7, ly], fill=acc, width=2)
    d.rounded_rectangle([cx1 + 6, ly - 18, W - 48, ly + 18], radius=9, fill=acc)
    d.text(((cx1 + 6 + W - 48) / 2, ly), _fmt(last), font=F(BLACK, 17), fill=(10, 10, 12), anchor='mm')
    # annotate biggest candle
    t, o, h, l, c, v = rows[big]
    bx = cx0 + step * (big + 0.5); move = (c / o - 1) * 100
    by = Y(h) if move >= 0 else Y(l)
    d.ellipse([bx - 30, by - 30, bx + 30, by + 30], outline=GOLD, width=4)
    label = note or f'{move:+.1f}% in one candle'
    lw = d.textlength(label, font=F(BLACK, 22)) + 32
    lx = min(max(bx - lw / 2, cx0), cx1 - lw)
    ly2 = by - 90 if move >= 0 and by - 90 > cy0 else min(by + 50, cy1 - 40)
    if move < 0 and by + 90 > cy1:
        ly2 = by - 90
    d.line([bx, by + (-30 if ly2 < by else 30), bx, ly2 + (40 if ly2 < by else 0)], fill=GOLD, width=3)
    d.rounded_rectangle([lx, ly2, lx + lw, ly2 + 40], radius=10, fill=GOLD)
    d.text((lx + lw / 2, ly2 + 20), label, font=F(BLACK, 22), fill=(16, 14, 8), anchor='mm')
    # time labels
    k = max(1, n // 5)
    for i in range(0, n, k):
        dt = datetime.fromtimestamp(rows[i][0] / 1000, timezone.utc)
        lab = dt.strftime('%H:%M') if (rows[-1][0] - rows[0][0]) < 2 * 86400000 else dt.strftime('%b %d')
        d.text((cx0 + step * (i + 0.5), bot - 22), lab, font=F(MED, 16), fill=DIM, anchor='mm')
    # stats tiles
    hh = max(r[2] for r in rows); ll = min(r[3] for r in rows)
    tiles = [('HIGH', _fmt(hh), WHITE), ('LOW', _fmt(ll), WHITE), ('CHANGE', f'{ch:+.1f}%', acc)]
    tw = (W - 80 - 40) / 3
    for i, (a, b, col) in enumerate(tiles):
        x0 = 40 + i * (tw + 20)
        d.rounded_rectangle([x0, 1170, x0 + tw, 1262], radius=20, fill=PANEL, outline=LINE, width=2)
        d.text((x0 + 24, 1188), a + f' · {tf_label.split(" · ")[0].upper()}', font=F(SEMI, 15), fill=DIM)
        d.text((x0 + 24, 1214), b, font=F(BLACK, 34), fill=col)
    d.text((60, 1300), 'Every chart hides a story', font=F(MED, 20), fill=MUT, anchor='lm')
    d.text((W - 60, 1300), f'Data: {source} · real candles', font=F(MED, 17), fill=DIM, anchor='rm')
    return _png(im)


def headline_card(title, source, keyfact='', tag='BREAKING', tag_col=RED):
    im = _bg(GOLD)
    d = ImageDraw.Draw(im)
    _header(d, tag, tag_col)
    nums = re.findall(r'[\$€£]\s?\d[\d,.]*\s?(?:[kmbt]|million|billion|trillion)?', title, re.I)
    big = ''
    if nums:
        def val(s):
            v = float(re.sub(r'[^\d.]', '', s.replace(',', '')) or 0)
            m = {'k': 1e3, 'm': 1e6, 'million': 1e6, 'b': 1e9, 'billion': 1e9, 't': 1e12, 'trillion': 1e12}
            u = re.findall(r'(million|billion|trillion|[kmbt])\s*$', s.strip(), re.I)
            return v * m.get(u[0].lower(), 1) if u else v
        b = max(nums, key=val); v = val(b)
        big = (f'${v/1e9:.3g}B' if v >= 1e9 else f'${v/1e6:.3g}M' if v >= 1e6 else f'${v:,.0f}')
    y = 200
    if big:
        d.text((60, y), big, font=F(BLACK, 230), fill=GOLD)
        y += 280
        d.line([60, y, 260, y], fill=GOLD, width=6); y += 40
    else:
        y = 260
    y = _headline(d, title, y, sizes=(72, 64, 56, 50), maxlines=5 if not big else 4)
    if keyfact:
        y += 24
        f = F(MED, 30); words = keyfact.split(); line = ''
        for w in words:
            if d.textlength(line + ' ' + w, font=f) > 940:
                d.text((60, y), line.strip(), font=f, fill=MUT); y += 42; line = w
            else:
                line += ' ' + w
            if y > 1180:
                break
        if y <= 1180:
            d.text((60, y), line.strip(), font=f, fill=MUT)
    d.line([60, 1255, W - 60, 1255], fill=LINE, width=2)
    d.text((60, 1300), 'Every chart hides a story', font=F(MED, 20), fill=MUT, anchor='lm')
    d.text((W - 60, 1300), f'Source: {source}', font=F(MED, 18), fill=DIM, anchor='rm')
    return _png(im)
