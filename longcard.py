"""Chain Secrets 'true story' long card for X: one tall 1080-wide image (headline, 3 stats, story, real chart, lesson, question).
render(spec, rows) -> jpg bytes. rows = [(ms, o, h, l, c, vol), ...] real candles; spec['chart'] = {'title','mark','label','from','to'}."""
import io, os, json, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = os.path.dirname(os.path.abspath(__file__))
W = 1080; M = 72
BG = (13, 17, 26); PANEL = (22, 27, 40); TXT = (232, 236, 244); MUTED = (150, 158, 176); GOLD = (255, 196, 46); UP = (38, 194, 160); DN = (246, 70, 93)
_FN = {'black': 'InterDisplay-Black.otf', 'xbold': 'InterDisplay-ExtraBold.otf', 'bold': 'InterDisplay-Bold.otf', 'semi': 'Inter-SemiBold.otf',
       'reg': 'Inter-Regular.otf', 'med': 'Inter-Medium.otf'}
_fc = {}
def font(w, s):
    if (w, s) not in _fc: _fc[(w, s)] = ImageFont.truetype(os.path.join(ROOT, 'fonts', _FN[w]), s)
    return _fc[(w, s)]
def wrap(d, text, f, maxw):
    out, line = [], ''
    for w in str(text).split(' '):
        t = (line + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw: line = t
        else: out.append(line); line = w
    return [l for l in out + [line] if l]

def _draw(S, rows, H=None, dry=False):
    im = Image.new('RGB', (W, H or 5000), BG); d = ImageDraw.Draw(im)
    if not dry:
        g = Image.new('RGB', im.size, BG); gd = ImageDraw.Draw(g)
        gd.ellipse((W - 600, -380, W + 300, 420), fill=(48, 40, 18)); gd.ellipse((-400, im.size[1] - 500, 500, im.size[1] + 300), fill=(14, 46, 42))
        im = Image.blend(im, g.filter(ImageFilter.GaussianBlur(170)), .85); d = ImageDraw.Draw(im)
        try:
            logo = Image.open(os.path.join(ROOT, 'x_logo.png')).convert('RGB').resize((112, 112)); mask = Image.new('L', (112, 112), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, 111, 111), 26, fill=255); im.paste(logo, (M, 60), mask)
        except Exception as e: print('logo', e)
    d.text((M + 136, 92), 'Chain Secrets', font=font('black', 40), fill=TXT, anchor='lm')
    d.text((M + 136, 140), '@thechainsecrets', font=font('med', 30), fill=MUTED, anchor='lm')
    y = 230
    d.text((M, y), S.get('kicker') or 'TRUE STORY', font=font('black', 30), fill=GOLD); y += 54
    ft = font('black', 76)
    for ln in wrap(d, S['title'], ft, W - 2 * M): d.text((M, y), ln, font=ft, fill=TXT); y += int(ft.size * 1.08)
    if S.get('tag'): y += 10; d.text((M, y), S['tag'].upper(), font=font('bold', 26), fill=MUTED); y += 44
    y += 16; d.line((M, y, M + 120, y), fill=GOLD, width=6); y += 40
    st = [s for s in (S.get('stats') or []) if isinstance(s, dict) and s.get('value')][:3]       # {'value', 'label', 'color': red|gold|green}
    if st:
        n = len(st); gap = 20; tw = (W - 2 * M - gap * (n - 1)) / n
        for k, s_ in enumerate(st):
            v, lab = str(s_['value']), str(s_.get('label', '')); x = M + k * (tw + gap); col = {'green': UP, 'red': DN}.get(s_.get('color'), GOLD)
            d.rounded_rectangle((x, y, x + tw, y + 150), 22, fill=PANEL)
            fv = font('black', 52)
            while d.textlength(v, font=fv) > tw - 30 and fv.size > 24: fv = font('black', fv.size - 2)
            d.text((x + tw / 2, y + 58), v, font=fv, fill=col, anchor='mm')
            for j, ln in enumerate(wrap(d, lab, font('semi', 22), tw - 24)[:2]): d.text((x + tw / 2, y + 102 + j * 26), ln, font=font('semi', 22), fill=MUTED, anchor='mm')
        y += 150 + 44
    fb, fh = font('reg', 37), font('bold', 37); lh = int(fb.size * 1.42)
    for p in S.get('story') or []:
        hl = p.startswith('!'); p = p.lstrip('!').strip(); f = fh if hl else fb
        for ln in wrap(d, p, f, W - 2 * M): d.text((M, y), ln, font=f, fill=GOLD if hl else TXT); y += lh
        y += int(lh * .5)
    ch = S.get('chart')
    if ch and rows and len(rows) >= 8:
        O = [r[1] for r in rows]; Hh = [r[2] for r in rows]; L = [r[3] for r in rows]; C = [r[4] for r in rows]; n = len(C)
        h = 300; d.rounded_rectangle((M, y, W - M, y + h), 22, fill=PANEL)
        d.text((M + 28, y + 30), ch['title'], font=font('bold', 24), fill=MUTED, anchor='lm')
        px0, py0, px1, py1 = M + 28, y + 112, W - M - 28, y + h - 46
        lo, hi = min(L), max(Hh); pad = (hi - lo) * .04 or 1; lo -= pad; hi += pad
        step = (px1 - px0) / n; bw = max(2, step * .62)
        X = lambda i: px0 + step * (i + .5); Y = lambda v: py1 - (py1 - py0) * (v - lo) / (hi - lo)
        mk = max(0, min(n - 1, int(ch.get('mark', n - 1)))); mx = X(mk)
        d.line((mx, py0 - 8, mx, py1), fill=(120, 100, 40), width=2)
        for i in range(n):
            col = UP if C[i] >= O[i] else DN; x = X(i)
            d.line((x, Y(Hh[i]), x, Y(L[i])), fill=col, width=max(1, int(bw / 4)))
            y0, y1 = sorted((Y(O[i]), Y(C[i]))); d.rectangle((x - bw / 2, y0, x + bw / 2, max(y1, y0 + 2)), fill=col)
        d.ellipse((mx - 10, Y(Hh[mk]) - 26, mx + 10, Y(Hh[mk]) - 6), fill=GOLD)
        fl = font('black', 26); lw = d.textlength(ch['label'], font=fl); bx = min(max(mx - lw / 2 - 16, px0), px1 - lw - 32)
        d.rounded_rectangle((bx, py0 - 34, bx + lw + 32, py0 + 4), 12, fill=GOLD); d.text((bx + 16, py0 - 15), ch['label'], font=fl, fill=BG, anchor='lm')
        d.text((px0, y + h - 22), ch['from'], font=font('semi', 20), fill=MUTED, anchor='lm'); d.text((px1, y + h - 22), ch['to'], font=font('semi', 20), fill=MUTED, anchor='rm')
        y += h + 36
    if S.get('lesson'):
        y += 10; fl = font('xbold', 40); lines = wrap(d, S['lesson'], fl, W - 2 * M - 70)
        bh = 70 + len(lines) * 54 + 30
        d.rounded_rectangle((M, y, W - M, y + bh), 26, fill=PANEL, outline=(60, 52, 28), width=3)
        d.text((M + 36, y + 30), 'THE LESSON', font=font('black', 26), fill=GOLD)
        for k, ln in enumerate(lines): d.text((M + 36, y + 72 + k * 54), ln, font=fl, fill=TXT)
        y += bh + 40
    if S.get('question'):
        fq = font('xbold', 36); lines = wrap(d, S['question'], fq, W - 2 * M - 60); bh = 34 + len(lines) * 48 + 26
        d.rounded_rectangle((M, y, W - M, y + bh), 26, fill=GOLD)
        for k, ln in enumerate(lines): d.text((W / 2, y + 34 + k * 48 + 20), ln, font=fq, fill=BG, anchor='mm')
        y += bh + 34
    d.text((M, y), 'A true crypto & money story every day. Follow →', font=font('semi', 30), fill=MUTED); y += 70
    return y if dry else im

def render(S, rows=None):
    h = _draw(S, rows, dry=True); im = _draw(S, rows, H=max(1350, h + 30)).crop((0, 0, W, max(1350, h + 30)))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=93); return b.getvalue()

if __name__ == '__main__':
    import sys
    S = json.load(open(sys.argv[1])); open(sys.argv[2], 'wb').write(render(S, json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None)); print(sys.argv[2])
