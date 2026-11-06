"""Cartoon-style Short (1080x1920) — test: the bitcoin pizza. Original characters drawn in code.
python3 toon.py VOICEDIR still t1 t2..   |  python3 toon.py VOICEDIR render out.mp4"""
import sys, os, math, json, subprocess
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); FD = os.path.join(HERE, '..', 'fonts')
S = 2; W, H = 1080 * S, 1920 * S; FPS = 30
OUT = (28, 28, 36); SKIN = (255, 226, 196); GOLD = (255, 196, 40); RED = (232, 65, 72)
_F = {}
def F(n, z):
    k = (n, z)
    if k not in _F: _F[k] = ImageFont.truetype(os.path.join(FD, n), int(z))
    return _F[k]
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def out3(x): x = clamp(x); return 1 - (1 - x) ** 3
def outback(x): x = clamp(x); c = 1.8; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
def seg(t, a, b): return clamp((t - a) / max(1e-6, b - a))

# ---------------------------------------------------------------- timing from the voice files
def srt(p):
    out = []
    for b in open(p).read().strip().split('\n\n'):
        l = b.strip().split('\n'); a, bb = l[1].split(' --> ')
        f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + float(x[6:].replace(',', '.'))
        out.append((f(a), f(bb), ' '.join(l[2:])))
    return out
LEAD = .3
def load(vd):
    cues = srt(f'{vd}/p0.srt'); words = srt(f'{vd}/p0p_words.srt')
    sc = []
    for k, (a, b, _) in enumerate(cues):
        nxt = cues[k + 1][0] if k + 1 < len(cues) else 1e9
        sc.append({'a': a + LEAD, 'b': b + LEAD, 'w': [(x + LEAD, y + LEAD, t) for x, y, t in words if a - .05 <= x < nxt - .05]})
    for k, s in enumerate(sc):
        s['s0'] = 0 if k == 0 else s['a'] - .1
    for k, s in enumerate(sc): s['s1'] = sc[k + 1]['s0'] if k + 1 < len(sc) else s['b'] + 1.2
    return sc
def wt(s, word, default):
    for x, y, t in s['w']:
        if word.lower() in t.lower(): return x
    return default

# ---------------------------------------------------------------- drawing kit (all coordinates at 2x)
def blob(d, box, fill, w=10): d.ellipse(box, fill=fill, outline=OUT, width=w)
def person(d, x, y, z=1., shirt=(80, 160, 110), hair=(90, 60, 40), face='smile', cap=None, glasses=False, arm=0., look=0., t=0.):
    """x,y = feet centre. arm: 0 down, 1 raised. look: -1..1 eye direction"""
    bob = math.sin(t * 4) * 6 * z
    r = 150 * z; hy = y - 560 * z + bob
    # legs
    for dx in (-50, 50):
        d.rounded_rectangle([x + dx * z - 28 * z, y - 210 * z, x + dx * z + 28 * z, y], 24 * z, fill=(60, 70, 100), outline=OUT, width=int(9 * z))
        d.ellipse([x + dx * z - 46 * z, y - 30 * z, x + dx * z + 40 * z, y + 18 * z], fill=(50, 40, 40), outline=OUT, width=int(8 * z))
    # body
    d.rounded_rectangle([x - 120 * z, y - 420 * z + bob, x + 120 * z, y - 180 * z], 70 * z, fill=shirt, outline=OUT, width=int(10 * z))
    # arms
    for side in (-1, 1):
        sx, sy = x + side * 105 * z, y - 380 * z + bob
        a = arm if side == 1 else 0
        ex, ey = sx + side * (60 + 40 * a) * z, sy + (170 - 330 * a) * z
        d.line([sx, sy, ex, ey], fill=OUT, width=int(62 * z)); d.line([sx, sy, ex, ey], fill=shirt, width=int(44 * z))
        d.ellipse([ex - 34 * z, ey - 34 * z, ex + 34 * z, ey + 34 * z], fill=SKIN, outline=OUT, width=int(8 * z))
    # head
    blob(d, [x - r, hy - r, x + r, hy + r], SKIN, int(10 * z))
    if hair and not cap:
        d.chord([x - r, hy - r, x + r, hy + r * .6], 190, 350, fill=hair, outline=OUT, width=int(10 * z))
    if cap:
        d.chord([x - r * 1.02, hy - r * 1.08, x + r * 1.02, hy + r * .7], 180, 360, fill=cap, outline=OUT, width=int(10 * z))
        d.rounded_rectangle([x - r * 1.1, hy - r * .22, x + r * 1.45, hy - r * .02], 20 * z, fill=cap, outline=OUT, width=int(9 * z))
    # face
    blink = (t % 3.3) < .12
    ex_ = look * 14 * z
    for dx in (-52, 52):
        cx, cy = x + dx * z + ex_, hy + 10 * z
        if blink: d.line([cx - 22 * z, cy, cx + 22 * z, cy], fill=OUT, width=int(8 * z)); continue
        sh = 1.35 if face == 'shock' else 1
        d.ellipse([cx - 20 * z * sh, cy - 28 * z * sh, cx + 20 * z * sh, cy + 28 * z * sh], fill=OUT)
        d.ellipse([cx - 9 * z + 6 * z, cy - 18 * z, cx + 3 * z + 6 * z, cy - 6 * z], fill=(255, 255, 255))
    if glasses:
        for dx in (-52, 52):
            d.ellipse([x + dx * z - 46 * z, hy - 34 * z, x + dx * z + 46 * z, hy + 56 * z], outline=OUT, width=int(8 * z))
        d.line([x - 6 * z, hy + 6 * z, x + 6 * z, hy + 6 * z], fill=OUT, width=int(8 * z))
    my = hy + 80 * z
    if face == 'smile': d.arc([x - 50 * z, my - 40 * z, x + 50 * z, my + 30 * z], 20, 160, fill=OUT, width=int(9 * z))
    elif face == 'grin':
        d.chord([x - 60 * z, my - 40 * z, x + 60 * z, my + 50 * z], 0, 180, fill=(120, 30, 40), outline=OUT, width=int(9 * z))
    elif face == 'shock': d.ellipse([x - 26 * z, my - 20 * z, x + 26 * z, my + 46 * z], fill=(120, 30, 40), outline=OUT, width=int(8 * z))
    elif face == 'sad': d.arc([x - 45 * z, my, x + 45 * z, my + 60 * z], 200, 340, fill=OUT, width=int(9 * z))
    else: d.line([x - 34 * z, my + 10 * z, x + 34 * z, my + 10 * z], fill=OUT, width=int(9 * z))
    d.ellipse([x - 120 * z, hy + 40 * z, x - 80 * z, hy + 70 * z], fill=(255, 170, 160))
    d.ellipse([x + 80 * z, hy + 40 * z, x + 120 * z, hy + 70 * z], fill=(255, 170, 160))

def coin(d, x, y, r):
    d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD, outline=(150, 100, 10), width=max(3, int(r * .12)))
    d.ellipse([x - r * .72, y - r * .72, x + r * .72, y + r * .72], outline=(220, 150, 20), width=max(2, int(r * .08)))
    d.text((x, y + r * .04), '₿', font=F('DejaVuSansMono-Bold.ttf', r * 1.1), fill=(150, 95, 10), anchor='mm')
def pizza_box(d, x, y, z=1., open_=False):
    d.rounded_rectangle([x - 220 * z, y - 50 * z, x + 220 * z, y + 50 * z], 10, fill=(232, 205, 160), outline=OUT, width=int(9 * z))
    d.text((x, y), 'PIZZA', font=F('InterDisplay-Black.otf', 60 * z), fill=RED, anchor='mm')
def pizza(d, x, y, r, slice_gone=False):
    d.ellipse([x - r, y - r, x + r, y + r], fill=(220, 150, 70), outline=OUT, width=10)
    d.ellipse([x - r * .85, y - r * .85, x + r * .85, y + r * .85], fill=(250, 200, 80))
    for a, b in ((-.4, -.3), (.35, -.4), (-.2, .4), (.45, .3), (0, 0)):
        d.ellipse([x + a * r - r * .1, y + b * r - r * .1, x + a * r + r * .1, y + b * r + r * .1], fill=(200, 50, 50))
    for k in range(4):
        ang = k * math.pi / 4; d.line([x - math.cos(ang) * r * .85, y - math.sin(ang) * r * .85, x + math.cos(ang) * r * .85, y + math.sin(ang) * r * .85], fill=(200, 140, 60), width=6)
def room(d, wall, floor, night=True):
    d.rectangle([0, 0, W, H], fill=wall)
    d.rectangle([0, H * .7, W, H], fill=floor)
    d.rectangle([0, H * .7 - 12, W, H * .7], fill=tuple(int(c * .7) for c in floor))
    wx, wy = W * .62, H * .14
    d.rounded_rectangle([wx, wy, wx + 620, wy + 700], 20, fill=(20, 30, 70) if night else (150, 210, 250), outline=OUT, width=14)
    if night:
        d.ellipse([wx + 380, wy + 80, wx + 520, wy + 220], fill=(250, 245, 210))
        for sx, sy in ((80, 120), (200, 330), (120, 520), (430, 470), (300, 160)): d.ellipse([wx + sx, wy + sy, wx + sx + 12, wy + sy + 12], fill=(255, 255, 255))
    d.line([wx + 310, wy, wx + 310, wy + 700], fill=OUT, width=12); d.line([wx, wy + 350, wx + 620, wy + 350], fill=OUT, width=12)
def desk(d, x, y, screen=(60, 140, 230), z=1.):
    _desk(d, x, y, screen, z)
def _desk(d, x, y, screen, z):
    q = lambda a, b, c, e: [x + a * z, y + b * z, x + c * z, y + e * z]
    d.rounded_rectangle(q(-520, -40, 520, 20), 10, fill=(150, 100, 60), outline=OUT, width=10)
    for dx in (-460, 440): d.rectangle(q(dx, 20, dx + 30, 520), fill=(120, 80, 50), outline=OUT, width=8)
    d.rounded_rectangle(q(-300, -480, 300, -100), 20, fill=(40, 40, 50), outline=OUT, width=10)
    d.rectangle(q(-270, -450, 270, -130), fill=screen)
    d.rectangle(q(-30, -100, 30, -40), fill=(40, 40, 50))
def _old_desk(d, x, y, screen=(60, 140, 230)):
    d.rounded_rectangle([x - 520, y - 40, x + 520, y + 20], 10, fill=(150, 100, 60), outline=OUT, width=10)
    for dx in (-460, 440): d.rectangle([x + dx, y + 20, x + dx + 30, y + 520], fill=(120, 80, 50), outline=OUT, width=8)
    d.rounded_rectangle([x - 300, y - 480, x + 300, y - 100], 20, fill=(40, 40, 50), outline=OUT, width=10)
    d.rectangle([x - 270, y - 450, x + 270, y - 130], fill=screen)
    d.rectangle([x - 30, y - 100, x + 30, y - 40], fill=(40, 40, 50))
def bubble(d, x, y, w, h, txt, f, tail=(0, 1)):
    d.rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], 50, fill=(255, 255, 255), outline=OUT, width=10)
    tx, ty = x + tail[0] * w * .25, y + h / 2
    d.polygon([(tx - 40, ty - 8), (tx + 40, ty - 8), (tx + tail[0] * 80, ty + 90)], fill=(255, 255, 255), outline=OUT)
    d.line([tx - 40, ty - 4, tx + tail[0] * 80, ty + 90, tx + 40, ty - 4], fill=OUT, width=10)
    d.rectangle([tx - 34, ty - 18, tx + 34, ty - 2], fill=(255, 255, 255))
    lines = txt.split('\n')
    for i, ln in enumerate(lines):
        d.text((x, y + (i - (len(lines) - 1) / 2) * f.size * 1.2), ln, font=f, fill=OUT, anchor='mm')
def pill(d, txt):
    f = F('InterDisplay-Black.otf', 64); tw = f.getlength(txt)
    d.rounded_rectangle([W / 2 - tw / 2 - 50, 250, W / 2 + tw / 2 + 50, 370], 60, fill=(20, 20, 26, 230))
    d.text((W / 2, 312), txt, font=f, fill=(255, 255, 255), anchor='mm')

# ---------------------------------------------------------------- scenes
LASZLO = dict(shirt=(80, 160, 110), hair=(110, 70, 40), glasses=True)
def scene(d, k, s, t, img):
    lt = t - s['s0']; dur = s['s1'] - s['s0']
    if k == 0:
        room(d, (90, 80, 140), (120, 90, 70)); desk(d, W * .68, H * .74, z=1.4)
        person(d, W * .3, H * .98, 2.0, face='sad', t=t, look=1, **LASZLO)
        u = out3(seg(t, wt(s, 'hungry', s['s0'] + 1.5), wt(s, 'hungry', s['s0'] + 1.5) + .4))
        if u > 0:
            bubble(d, W * .58, H * .3, 620, 460, '', F('InterDisplay-Black.otf', 60), tail=(-1, 1)); pizza(d, W * .58, H * .3, 160 * outback(u))
        pill(d, 'MAY 18, 2010')
    elif k == 1:
        d.rectangle([0, 0, W, H], fill=(40, 44, 60))
        d.rounded_rectangle([140, 600, W - 140, 2700], 40, fill=(245, 245, 240), outline=OUT, width=16)
        d.rectangle([140, 600, W - 140, 780], fill=(60, 110, 170)); d.text((W / 2, 690), 'BITCOIN FORUM · MAY 18, 2010', font=F('InterDisplay-Black.otf', 62), fill=(255, 255, 255), anchor='mm')
        person(d, 420, 1360, .55, face='smile', t=t, **LASZLO)
        d.text((700, 1060), 'laszlo', font=F('InterDisplay-Black.otf', 76), fill=OUT, anchor='lm')
        txt = ["I'll pay 10,000", "bitcoins for a", "couple of pizzas.."]
        n = int(sum(len(x) for x in txt) * out3(seg(t, s['s0'] + .3, s['b'] - .3)))
        y = 1550; c = 0
        for ln in txt:
            show = ln[:max(0, min(len(ln), n - c))]; c += len(ln)
            d.text((260, y), show, font=F('InterDisplay-Black.otf', 120), fill=OUT, anchor='lm'); y += 170
        d.text((260, 2560), 'real post, May 18 2010', font=F('Inter-SemiBold.otf', 50), fill=(130, 130, 140), anchor='lm')
    elif k == 2:
        room(d, (200, 150, 90), (110, 80, 60), night=False); desk(d, W * .34, H * .74, (230, 230, 120), z=1.4)
        person(d, W * .7, H * .98, 2.0, shirt=(210, 70, 70), cap=(40, 90, 200), face='grin', arm=out3(seg(t, s['s0'] + .6, s['s0'] + 1)), t=t, look=-1)
        u = outback(seg(t, wt(s, 'deal', s['s0'] + 1.2), wt(s, 'deal', s['s0'] + 1.2) + .35))
        if u > .05: bubble(d, W * .38, H * .3, 700 * u + 10, 340 * u + 10, 'DEAL!', F('InterDisplay-Black.otf', 170 * u + 1), tail=(1, 1))
        pill(d, 'MAY 22, 2010')
    elif k == 3:
        d.rectangle([0, 0, W, H], fill=(230, 210, 170)); d.rectangle([0, H * .78, W, H], fill=(150, 160, 150))
        d.rounded_rectangle([W * .08, H * .22, W * .46, H * .78], 20, fill=(140, 80, 50), outline=OUT, width=16)
        d.ellipse([W * .4, H * .5, W * .43, H * .52], fill=GOLD, outline=OUT, width=6)
        sl = out3(seg(t, s['s0'], s['s0'] + .7))
        person(d, W * .28, H * .98, 1.9, face='grin', t=t, arm=.4, **LASZLO)
        dx = W * .72 + (1 - sl) * 600
        person(d, dx, H * .98, 1.9, shirt=(220, 60, 60), cap=(220, 60, 60), hair=None, face='smile', t=t + 1, look=-1)
        for i in range(2): pizza_box(d, dx - 230, H * .98 - 700 - i * 150, 1.5)
        pill(d, 'MAY 22, 2010')
    elif k == 4:
        room(d, (90, 80, 140), (120, 90, 70))
        d.rounded_rectangle([W * .1, H * .64, W * .9, H * .68], 10, fill=(150, 100, 60), outline=OUT, width=10)
        n = int(60 * out3(seg(t, s['s0'], s['s0'] + 1.2)))
        for i in range(n):
            r_, c_ = divmod(i, 12)
            coin(d, W * .2 + c_ * 115 + (r_ % 2) * 55, H * .62 - r_ * 70, 70)
        u = outback(seg(t, wt(s, 'forty', s['s0'] + 1.5), wt(s, 'forty', s['s0'] + 1.5) + .35))
        if u > 0:
            d.rounded_rectangle([W / 2 - 360 * u, 900 - 160 * u, W / 2 + 360 * u, 900 + 160 * u], 40, fill=(255, 255, 255), outline=OUT, width=12)
            d.text((W / 2, 900), '$41', font=F('InterDisplay-Black.otf', 240 * u + 1), fill=(40, 150, 70), anchor='mm')
        pizza(d, W * .5, H * .8, 260)
        pill(d, '10,000 BTC')
    elif k == 5:
        d.rectangle([0, 0, W, H], fill=(20, 18, 30))
        g = out3(seg(t, s['s0'], s['b']))
        for i in range(int(14 + 90 * g)):
            a = i * 2.39996; rr = 60 + 30 * math.sqrt(i) * 3.2
            coin(d, W / 2 + math.cos(a) * rr * .9, H * .47 + math.sin(a) * rr * .5, 70 + (i % 3) * 8)
        v = int(41 + (766_000_000 - 41) * out3(seg(t, s['s0'] + .2, s['b'] - .2)) ** 3)
        f = F('InterDisplay-Black.otf', 170); d.text((W / 2, 900), f'${v:,}', font=f, fill=GOLD, anchor='mm', stroke_width=10, stroke_fill=OUT)
        person(d, W * .5, H * 1.02, 1.6, face='shock', t=t, arm=1, **LASZLO)
        pill(d, 'TODAY')
    elif k == 6:
        d.rectangle([0, 0, W, H], fill=(250, 220, 90))
        for i in range(16):
            a = i * math.pi / 8 + t * .2
            d.polygon([(W / 2, H * .45), (W / 2 + math.cos(a) * 2600, H * .45 + math.sin(a) * 2600), (W / 2 + math.cos(a + .2) * 2600, H * .45 + math.sin(a + .2) * 2600)], fill=(255, 235, 140))
        u = outback(seg(t, s['s0'], s['s0'] + .5))
        pizza(d, W / 2, H * .45, 420 * u + 1)
        d.rounded_rectangle([W * .58, H * .52, W * .9, H * .6], 30, fill=(255, 255, 255), outline=OUT, width=12)
        d.text((W * .74, H * .56), '$766M', font=F('InterDisplay-Black.otf', 120), fill=(40, 150, 70), anchor='mm')
    else:
        d.rectangle([0, 0, W, H], fill=(16, 16, 22))
        lg = Image.open(os.path.join(HERE, '..', '..', 'studio', 'chain_secrets_profile.png')).convert('RGBA').resize((560, 560))
        m = Image.new('L', (560, 560), 0); ImageDraw.Draw(m).ellipse([0, 0, 559, 559], fill=255); lg.putalpha(m)
        img.alpha_composite(lg, (W // 2 - 280, 1100))
        d.text((W / 2, 1900), 'FOLLOW', font=F('InterDisplay-Black.otf', 150), fill=(255, 255, 255), anchor='mm')
        d.text((W / 2, 2080), 'CHAIN SECRETS', font=F('InterDisplay-Black.otf', 150), fill=RED, anchor='mm')

def caption(d, sc, t, k_=0):
    for s in sc:
        for i, (a, b, w) in enumerate(s['w']):
            nb = s['w'][i + 1][0] if i + 1 < len(s['w']) else b + .25
            if a - .03 <= t < nb:
                w = w.strip('".,!?').upper()
                f = F('InterDisplay-Black.otf', 170); sc_ = 1 + .12 * math.exp(-(t - a) * 14)
                f = F('InterDisplay-Black.otf', 170 * sc_)
                d.text((W / 2, 2950 if k_ == 1 else H * .45), w, font=f, fill=(255, 255, 255), anchor='mm', stroke_width=16, stroke_fill=OUT)
                return

def frame(sc, t):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 255)); d = ImageDraw.Draw(img)
    k = next((i for i, s in enumerate(sc) if s['s0'] <= t < s['s1']), len(sc) - 1)
    scene(d, k, sc[k], t, img)
    if k < len(sc) - 1: caption(d, sc, t, k)
    lt = t - sc[k]['s0']
    im = img.convert('RGB').resize((1080, 1920), Image.LANCZOS)
    if k > 0 and lt < .12:          # quick flash-cut between scenes
        im = Image.blend(im, Image.new('RGB', im.size, (255, 255, 255)), (1 - lt / .12) * .35)
    return im

if __name__ == '__main__':
    sc = load(sys.argv[1]); mode = sys.argv[2]
    if mode == 'still':
        ims = [frame(sc, float(x)).resize((270, 480)) for x in sys.argv[3:]]
        sh = Image.new('RGB', (270 * len(ims), 480))
        for i, im in enumerate(ims): sh.paste(im, (270 * i, 0))
        sh.save(os.environ.get('SHEET', 'sheet.jpg'), quality=85)
    else:
        dur = sc[-1]['s1']; out = sys.argv[3]
        p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1080x1920', '-r', str(FPS), '-i', '-',
                              '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
        for i in range(int(dur * FPS)): p.stdin.write(frame(sc, i / FPS).tobytes())
        p.stdin.close(); p.wait(); print(out, dur)
