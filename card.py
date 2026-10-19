"""Chain Secrets post images, 1080x1350, drawn with Pillow.
Card types: chart (real candles), stat (one giant number), timeline, versus, quote, alert (hacks), headline (fallback)."""
import io, os, re
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H = 1080, 1350
ROOT = os.path.dirname(os.path.abspath(__file__))
_f = {}


def F(name, size):
    if (name, size) not in _f:
        _f[(name, size)] = ImageFont.truetype(os.path.join(ROOT, 'fonts', name + '.otf'), size)
    return _f[(name, size)]


BLACK, XB, BOLD, ITAL, SEMI, MED, REG = ('InterDisplay-Black', 'InterDisplay-ExtraBold', 'InterDisplay-Bold', 'InterDisplay-BoldItalic',
                                         'Inter-SemiBold', 'Inter-Medium', 'Inter-Regular')
BG1, BG2 = (14, 17, 25), (6, 7, 11)
PANEL, LINE = (17, 21, 31), (34, 40, 56)
WHITE, MUT, DIM = (241, 243, 248), (142, 151, 170), (82, 90, 108)
GOLD, RED, GRN = (232, 181, 64), (239, 68, 80), (38, 210, 160)
BLUE, PURPLE, ORANGE = (77, 132, 255), (139, 92, 246), (249, 140, 50)
TAGS = {'BREAKING': RED, 'HACK': RED, 'EXPLOIT': RED, 'ARREST': PURPLE, 'LAWSUIT': PURPLE, 'REGULATION': BLUE, 'COURT': PURPLE,
        'ETF': BLUE, 'MARKET': GRN, 'PRICE ALERT': RED, 'SCAM': ORANGE, 'WHALE': (20, 184, 166), 'TRUE STORY': GOLD,
        'CHART': GOLD, 'MYSTERY': PURPLE}
NUM = re.compile(r'^[\$€£]?\d[\d,.]*[%kKmMbBxX]?\+?$|^(million|billion|trillion|record|years?|%)$', re.I)
_logo = None


def tag_color(tag):
    return TAGS.get((tag or '').upper(), RED)


def logo(size):
    global _logo
    if _logo is None:
        _logo = Image.open(os.path.join(ROOT, 'assets', 'logo.png')).convert('RGB')
    im = _logo.resize((size, size), Image.LANCZOS)
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 4, fill=255)
    return im, m


def canvas(accent, glow_box=(0.1, 0.36, 1.1, 0.98), strength=0.20):
    grad = Image.linear_gradient('L').resize((W, H))
    im = Image.composite(Image.new('RGB', (W, H), BG2), Image.new('RGB', (W, H), BG1), grad)
    g = Image.new('RGB', (W, H), (0, 0, 0))
    x0, y0, x1, y1 = glow_box
    ImageDraw.Draw(g).ellipse([W * x0, H * y0, W * x1, H * y1], fill=tuple(int(v * strength) for v in accent))
    im = ImageChops.add(im, g.filter(ImageFilter.GaussianBlur(170)))
    d = ImageDraw.Draw(im)
    for yy in range(160, H - 120, 36):
        for xx in range(30, W, 36):
            d.point((xx, yy), fill=(24, 28, 38))
    return im


def header(im, tag, when=None):
    d = ImageDraw.Draw(im)
    lg, m = logo(70)
    im.paste(lg, (56, 44), m)
    d.text((142, 50), 'CHAIN SECRETS', font=F(BLACK, 30), fill=WHITE)
    d.text((143, 88), '@thechainsecrets', font=F(MED, 18), fill=MUT)
    tag = (tag or 'BREAKING').upper(); col = tag_color(tag)
    tw = d.textlength(tag, font=F(BLACK, 22)); x1 = W - 56; x0 = x1 - tw - 46
    d.rounded_rectangle([x0, 52, x1, 94], radius=21, fill=col)
    d.text(((x0 + x1) / 2, 73), tag, font=F(BLACK, 22), fill=(255, 255, 255) if col != GOLD else (20, 16, 6), anchor='mm')
    when = when or datetime.now(timezone.utc)
    d.text((x1, 108), when.strftime('%b %d, %Y · %H:%M UTC').upper(), font=F(SEMI, 15), fill=DIM, anchor='ra')
    return d


FOOTER_LEFT = ''   # set by the caller: the reply idea goes here on non-chart cards


def footer(d, right):
    """Bottom strip: the post's punchline as a gold-barred italic pull-quote (left) and the source (right)."""
    d.line([56, 1262, W - 56, 1262], fill=LINE, width=2)
    rw = d.textlength(right, font=F(MED, 17))
    d.text((W - 56, 1302), right, font=F(MED, 17), fill=DIM, anchor='rm')
    txt = (FOOTER_LEFT or '').strip().strip('"“”')
    if not txt:
        return
    maxw = W - 112 - rw - 60
    for size in (22, 20, 18, 16):
        lines = wrap_lines(d, txt, F(ITAL, size), maxw)
        if len(lines) <= 2:
            break
    lines = lines[:2]
    if sum(len(l) for l in lines) < len(txt.split()) and lines[-1]:
        lines[-1][-1] += '…'
    lh = size * 1.3; h = lh * len(lines)
    y0 = 1302 - h / 2
    d.rounded_rectangle([56, y0 + 2, 61, y0 + h - 2], radius=2, fill=GOLD)
    for i, ln in enumerate(lines):
        d.text((76, y0 + i * lh), ' '.join(ln), font=F(ITAL, size), fill=(214, 218, 228))


def wrap_lines(d, text, font, maxw):
    lines, cur = [], []
    for w in text.split():
        if cur and d.textlength(' '.join(cur + [w]), font=font) > maxw:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def headline(d, text, y, maxw=968, sizes=(68, 60, 54, 48, 44), maxlines=3, x=56, gold_nums=True, color=WHITE):
    for s in sizes:
        f = F(BLACK, s); lines = wrap_lines(d, text, f, maxw)
        if len(lines) <= maxlines:
            break
    for ln in lines[:maxlines]:
        xx = x
        for w in ln:
            col = GOLD if gold_nums and NUM.match(w.strip(',.:;!?()"\'’')) else color
            d.text((xx, y), w, font=f, fill=col)
            xx += d.textlength(w + ' ', font=f)
        y += int(s * 1.13)
    return y


def para(d, text, y, font, color, maxw=968, x=56, lh=1.4, maxy=1240):
    for ln in wrap_lines(d, text, font, maxw):
        if y > maxy:
            break
        d.text((x, y), ' '.join(ln), font=font, fill=color); y += int(font.size * lh)
    return y


def fmt(v):
    if v >= 1000:
        return f'${v:,.0f}'
    if v >= 1:
        return f'${v:,.2f}'
    return f'${v:.4g}'


def png(im):
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()


def glow_text(im, xy, text, font, color, blur=26, anchor='la'):
    g = Image.new('RGB', im.size, (0, 0, 0))
    ImageDraw.Draw(g).text(xy, text, font=font, fill=tuple(int(c * 0.55) for c in color), anchor=anchor)
    im.paste(ImageChops.add(im, g.filter(ImageFilter.GaussianBlur(blur))))
    ImageDraw.Draw(im).text(xy, text, font=font, fill=color, anchor=anchor)


def fit_font(d, text, name, start, maxw, minsize=60):
    s = start
    while s > minsize and d.textlength(text, font=F(name, s)) > maxw:
        s -= 6
    return F(name, s)


# ---------------------------------------------------------------- CHART
def chart_card(title, coin, rows, tf_label, tag='BREAKING', source='CoinGecko', note=None):
    """rows: (t_ms, o, h, l, c, vol|None) oldest first — real candles."""
    first, last = rows[0][1], rows[-1][4]; ch = (last / first - 1) * 100; up = ch >= 0; acc = GRN if up else RED
    im = canvas(acc); d = header(im, tag)
    y = headline(d, title, 140) + 6
    nm = f'{coin["name"]} ({coin["sym"]})'
    d.text((56, y), nm, font=F(BOLD, 32), fill=WHITE)
    px = 56 + d.textlength(nm + '  ', font=F(BOLD, 32))
    d.text((px, y), fmt(last), font=F(BOLD, 32), fill=WHITE); px += d.textlength(fmt(last) + '  ', font=F(BOLD, 32))
    chip = f'{"▲" if up else "▼"} {abs(ch):.1f}%'; cw = d.textlength(chip, font=F(BLACK, 24)) + 28
    d.rounded_rectangle([px, y + 1, px + cw, y + 40], radius=12, fill=tuple(int(v * 0.22) for v in acc), outline=acc, width=2)
    d.text((px + cw / 2, y + 21), chip, font=F(BLACK, 24), fill=acc, anchor='mm')
    d.text((px + cw + 14, y + 21), tf_label, font=F(MED, 19), fill=MUT, anchor='lm')
    top = max(y + 68, 460); bot = 1140
    d.rounded_rectangle([36, top, W - 36, bot], radius=28, fill=PANEL, outline=LINE, width=2)
    cx0, cx1 = 66, W - 156; has_v = any(r[5] for r in rows)
    cy0, cy1 = top + 46, bot - (128 if has_v else 64)
    hi = max(r[2] for r in rows); lo = min(r[3] for r in rows); pad = (hi - lo) * 0.10 or hi * 0.01; hi += pad; lo -= pad
    Y = lambda p: cy1 - (p - lo) / (hi - lo) * (cy1 - cy0)
    n = len(rows); step = (cx1 - cx0) / n; bw = max(3, step * 0.62)
    for i in range(5):
        p = lo + (hi - lo) * i / 4; yy = Y(p)
        d.line([cx0, yy, cx1, yy], fill=(28, 33, 46), width=1)
        d.text((cx1 + 14, yy), fmt(p), font=F(MED, 17), fill=DIM, anchor='lm')
    vmax = max((r[5] or 0) for r in rows) or 1
    big = max(range(n), key=lambda i: abs(rows[i][4] - rows[i][1]) / rows[i][1])
    for i, (t, o, h, l, c, v) in enumerate(rows):
        x = cx0 + step * (i + 0.5); col = GRN if c >= o else RED
        d.line([x, Y(h), x, Y(l)], fill=col, width=2 if bw > 5 else 1)
        y0, y1 = sorted((Y(o), Y(c))); d.rectangle([x - bw / 2, y0, x + bw / 2, max(y1, y0 + 2)], fill=col)
        if has_v and v:
            vh = v / vmax * 66; d.rectangle([x - bw / 2, bot - 38 - vh, x + bw / 2, bot - 38], fill=tuple(int(cc * 0.42) for cc in col))
    ly = Y(last)
    for xx in range(cx0, int(cx1), 14):
        d.line([xx, ly, xx + 7, ly], fill=acc, width=2)
    d.rounded_rectangle([cx1 + 6, ly - 18, W - 44, ly + 18], radius=9, fill=acc)
    d.text(((cx1 + 6 + W - 44) / 2, ly), fmt(last), font=F(BLACK, 16), fill=(8, 10, 12), anchor='mm')
    t, o, h, l, c, v = rows[big]; bx = cx0 + step * (big + 0.5); mv = (c / o - 1) * 100
    by = Y(h) if mv >= 0 else Y(l)
    d.ellipse([bx - 30, by - 30, bx + 30, by + 30], outline=GOLD, width=4)
    label = note or f'{mv:+.1f}% in one candle'; lw = d.textlength(label, font=F(BLACK, 21)) + 30
    lx = min(max(bx - lw / 2, cx0), cx1 - lw)
    ly2 = by - 92 if by - 92 > cy0 else by + 52
    d.line([bx, by + (-30 if ly2 < by else 30), bx, ly2 + (40 if ly2 < by else 0)], fill=GOLD, width=3)
    d.rounded_rectangle([lx, ly2, lx + lw, ly2 + 40], radius=10, fill=GOLD)
    d.text((lx + lw / 2, ly2 + 20), label, font=F(BLACK, 21), fill=(18, 14, 6), anchor='mm')
    k = max(1, n // 5); multi = (rows[-1][0] - rows[0][0]) >= 2 * 86400000
    for i in range(0, n, k):
        dt = datetime.fromtimestamp(rows[i][0] / 1000, timezone.utc)
        d.text((cx0 + step * (i + 0.5), bot - 20), dt.strftime('%b %d' if multi else '%H:%M'), font=F(MED, 15), fill=DIM, anchor='mm')
    hh = max(r[2] for r in rows); ll = min(r[3] for r in rows); span = tf_label.split(' · ')[0].upper()
    tw = (W - 72 - 40) / 3
    for i, (a, b, col) in enumerate([('HIGH', fmt(hh), WHITE), ('LOW', fmt(ll), WHITE), ('CHANGE', f'{ch:+.1f}%', acc)]):
        x0 = 36 + i * (tw + 20)
        d.rounded_rectangle([x0, 1158, x0 + tw, 1246], radius=20, fill=PANEL, outline=LINE, width=2)
        d.text((x0 + 22, 1174), f'{a} · {span}', font=F(SEMI, 15), fill=DIM)
        d.text((x0 + 22, 1198), b, font=F(BLACK, 33), fill=col)
    d.text((56, 1302), 'Every chart hides a story', font=F(MED, 20), fill=MUT, anchor='lm')
    d.text((W - 56, 1302), f'Data: {source} · real candles', font=F(MED, 17), fill=DIM, anchor='rm')
    return png(im)


def centered(make_bg, tag, body, top=150, bottom=1240):
    """Draw body(im, y0)->end_y twice: once to measure, once vertically centered between header and footer."""
    probe = make_bg(); header(probe, tag); end = body(probe, top)
    off = max(0, ((bottom - top) - (end - top)) / 2.2)
    im = make_bg(); header(im, tag); body(im, top + off)
    return im


# ---------------------------------------------------------------- STAT
def stat_card(title, value, label, keyfact='', tag='BREAKING', source=''):
    col = tag_color(tag); acc = GOLD if col in (GOLD, GRN) else col

    def body(im, y):
        d = ImageDraw.Draw(im); f = fit_font(d, value, BLACK, 260, 968, 90)
        glow_text(im, (52, y), value, f, GOLD if acc != RED else (255, 92, 104))
        d = ImageDraw.Draw(im); y += int(f.size * 1.08) + 20
        d.text((58, y), label.upper()[:40], font=F(BLACK, 36), fill=WHITE); y += 66
        d.rounded_rectangle([56, y, 196, y + 8], radius=4, fill=acc); y += 52
        y = headline(d, title, y, sizes=(60, 54, 48, 44), maxlines=4)
        if keyfact:
            y = para(d, keyfact, y + 20, F(MED, 32), MUT)
        return y
    im = centered(lambda: canvas(acc, (0.0, 0.08, 1.0, 0.7), 0.24), tag, body)
    footer(ImageDraw.Draw(im), f'Source: {source}' if source else 'Chain Secrets')
    return png(im)


# ---------------------------------------------------------------- TIMELINE
def timeline_card(title, steps, tag='TRUE STORY', source=''):
    """steps: [(date, text), ...] 3–5 items; the last one is the punchline."""
    col = tag_color(tag)
    im = canvas(col, (0.3, 0.3, 1.2, 1.0), 0.18); d = header(im, tag)
    y = headline(d, title, 150, sizes=(62, 56, 50, 46), maxlines=3) + 30
    steps = steps[:5]; avail = 1220 - y; gap = min(200, avail / max(1, len(steps)))
    lx = 92
    d.line([lx, y + 18, lx, y + gap * (len(steps) - 1) + 18], fill=LINE, width=4)
    for i, (date, text) in enumerate(steps):
        yy = y + i * gap; last = i == len(steps) - 1; c = (RED if col == RED else GOLD) if last else GOLD
        if last:
            d.ellipse([lx - 22, yy - 4, lx + 22, yy + 40], fill=c)
        else:
            d.ellipse([lx - 16, yy + 2, lx + 16, yy + 34], fill=BG1, outline=c, width=5)
        d.text((lx + 46, yy), date.upper()[:28], font=F(BLACK, 26), fill=c)
        para(d, text, yy + 38, F(BOLD if last else SEMI, 34 if last else 31), WHITE if last else (210, 214, 224),
             maxw=W - lx - 110, x=lx + 46, lh=1.25, maxy=yy + gap - 30)
    footer(d, f'Source: {source}' if source else 'Chain Secrets')
    return png(im)


# ---------------------------------------------------------------- VERSUS
def versus_card(title, left, right, keyfact='', tag='BREAKING', source=''):
    """left/right: (label, value). Right side is the 'twist' side."""
    def body(im, y):
        d = ImageDraw.Draw(im)
        y = headline(d, title, y, sizes=(64, 58, 52, 46), maxlines=3) + 40
        pw = (W - 112 - 30) / 2; ph = 470
        for i, ((lab, val), c) in enumerate([(left, GRN), (right, RED)]):
            x0 = 56 + i * (pw + 30); tint = tuple(int(v * 0.25) for v in c)
            d.rounded_rectangle([x0, y, x0 + pw, y + ph], radius=30, fill=PANEL, outline=c, width=3)
            d.rounded_rectangle([x0 + 3, y + 3, x0 + pw - 3, y + 72], radius=28, fill=tint)
            d.rectangle([x0 + 3, y + 40, x0 + pw - 3, y + 72], fill=tint)
            d.text((x0 + pw / 2, y + 38), lab.upper()[:22], font=F(BLACK, 26), fill=c, anchor='mm')
            f = fit_font(d, val, BLACK, 120, pw - 50, 44); lines = wrap_lines(d, val, f, pw - 50)
            yy = y + 72 + (ph - 72) / 2 - len(lines[:3]) * f.size * 0.58
            for ln in lines[:3]:
                d.text((x0 + pw / 2, yy), ' '.join(ln), font=f, fill=WHITE, anchor='ma'); yy += f.size * 1.15
        cx, cy = W / 2, y + ph / 2
        d.ellipse([cx - 48, cy - 48, cx + 48, cy + 48], fill=GOLD, outline=BG1, width=8)
        d.text((cx, cy), 'VS', font=F(BLACK, 34), fill=(20, 16, 6), anchor='mm')
        y += ph
        if keyfact:
            y = para(d, keyfact, y + 40, F(MED, 32), MUT)
        return y
    im = centered(lambda: canvas(GOLD, (0.0, 0.4, 1.0, 0.9), 0.14), tag, body)
    footer(ImageDraw.Draw(im), f'Source: {source}' if source else 'Chain Secrets')
    return png(im)


# ---------------------------------------------------------------- QUOTE
def quote_card(title, quote, speaker, tag='BREAKING', source=''):
    q = quote.strip(' "“”')

    def body(im, y):
        d = ImageDraw.Draw(im)
        d.text((44, y - 40), '“', font=F(BLACK, 280), fill=GOLD); y += 200
        for s in (66, 60, 54, 48, 42):
            lines = wrap_lines(d, q, F(ITAL, s), 940)
            if len(lines) <= 6:
                break
        for ln in lines[:6]:
            d.text((70, y), ' '.join(ln), font=F(ITAL, s), fill=WHITE); y += int(s * 1.22)
        d.text((70, y + 26), f'— {speaker}'[:48], font=F(BLACK, 34), fill=GOLD); y += 110
        d.line([56, y, W - 56, y], fill=LINE, width=2)
        return headline(d, title, y + 34, sizes=(42, 38, 34), maxlines=3, color=MUT)
    im = centered(lambda: canvas(GOLD, (0.0, 0.1, 0.9, 0.7), 0.18), tag, body)
    footer(ImageDraw.Draw(im), f'Source: {source}' if source else 'Chain Secrets')
    return png(im)


# ---------------------------------------------------------------- ALERT (hacks / exploits / outages)
def alert_card(title, amount, details, word='HACKED', source='', tag='HACK'):
    """details: [(label, value), ...] up to 3."""
    details = [x for x in details if x[1]][:3]

    def body(im, y):
        stamp = Image.new('RGBA', (760, 200), (0, 0, 0, 0)); sd = ImageDraw.Draw(stamp)
        sd.rounded_rectangle([6, 6, 754, 194], radius=24, outline=(255, 80, 92, 255), width=12)
        f = fit_font(ImageDraw.Draw(im), word.upper(), BLACK, 130, 680, 60)
        sd.text((380, 100), word.upper(), font=f, fill=(255, 80, 92, 255), anchor='mm')
        stamp = stamp.rotate(-6, expand=True, resample=Image.BICUBIC)
        im.paste(stamp, ((W - stamp.width) // 2, int(y)), stamp); y += stamp.height + 10
        d = ImageDraw.Draw(im)
        if amount:
            f = fit_font(d, amount, BLACK, 200, 968, 80)
            glow_text(im, (W / 2, y), amount, f, WHITE, 30, 'ma'); d = ImageDraw.Draw(im); y += int(f.size * 1.1) + 20
        y = headline(d, title, y, sizes=(54, 48, 44, 40), maxlines=3) + 26
        if details:
            tw = (W - 72 - 20 * (len(details) - 1)) / len(details)
            for i, (a, b) in enumerate(details):
                x0 = 36 + i * (tw + 20)
                d.rounded_rectangle([x0, y, x0 + tw, y + 104], radius=20, fill=PANEL, outline=LINE, width=2)
                d.text((x0 + 22, y + 18), a.upper(), font=F(SEMI, 15), fill=DIM)
                d.text((x0 + 22, y + 46), str(b), font=fit_font(d, str(b), BLACK, 32, tw - 40, 16), fill=WHITE)
            y += 104
        return y

    def bg():
        im = canvas(RED, (0.0, 0.1, 1.0, 0.75), 0.30)
        band = Image.new('RGB', (W, 56), (20, 8, 10)); bd = ImageDraw.Draw(band)
        for x in range(-64, W + 64, 56):
            bd.polygon([(x, 56), (x + 28, 56), (x + 84, 0), (x + 56, 0)], fill=(150, 30, 40))
        im.paste(band, (0, 140)); return im
    im = centered(bg, tag, body, top=220)
    footer(ImageDraw.Draw(im), f'Source: {source}' if source else 'Chain Secrets')
    return png(im)


# ---------------------------------------------------------------- HEADLINE (fallback)
def big_money(text):
    nums = re.findall(r'[\$€£]\s?\d[\d,.]*\s?(?:million|billion|trillion|[kmbt]\b)?', text, re.I)
    if not nums:
        return ''

    def val(s):
        v = float(re.sub(r'[^\d.]', '', s.replace(',', '')) or 0)
        u = re.findall(r'(million|billion|trillion|[kmbt])\s*$', s.strip(), re.I)
        return v * {'k': 1e3, 'm': 1e6, 'million': 1e6, 'b': 1e9, 'billion': 1e9, 't': 1e12, 'trillion': 1e12}.get(u[0].lower(), 1) if u else v
    v = val(max(nums, key=val))
    return f'${v/1e9:.3g}B' if v >= 1e9 else f'${v/1e6:.3g}M' if v >= 1e6 else f'${v:,.0f}'


def headline_card(title, source, keyfact='', tag='BREAKING'):
    def body(im, y):
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([56, y, 196, y + 8], radius=4, fill=tag_color(tag)); y += 50
        y = headline(d, title, y, sizes=(84, 76, 68, 60, 54), maxlines=6)
        if keyfact:
            y = para(d, keyfact, y + 30, F(MED, 34), MUT)
        return y
    im = centered(lambda: canvas(tag_color(tag), (0.0, 0.2, 1.0, 0.9), 0.16), tag, body)
    footer(ImageDraw.Draw(im), f'Source: {source}')
    return png(im)
