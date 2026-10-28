"""Chain Secrets post looks (1080x1350): five modern styles for the same story, picked with a button.
Each takes the real title / key fact / source from the post; nothing here invents data (no fake likes, no fake numbers)."""
import hashlib, os
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import card
from card import F, W, H, BLACK, XB, BOLD, ITAL, SEMI, MED, WHITE, MUT, DIM, GOLD, RED, GRN, LINE, wrap_lines, png

MONO, MONOB = 'DejaVuSansMono', 'DejaVuSansMono-Bold'


def M(bold, size):
    return ImageFont.truetype(os.path.join(card.ROOT, 'fonts', (MONOB if bold else MONO) + '.ttf'), size)


def fit_lines(d, text, fontf, sizes, maxw, maxlines):
    """largest size whose wrapped text fits in maxlines. fontf(size)->font. Returns (font, lines)"""
    for s in sizes:
        f = fontf(s); lines = wrap_lines(d, text, f, maxw)
        if len(lines) <= maxlines:
            return f, lines
    return f, lines[:maxlines]


def now_stamp():
    return datetime.now(timezone.utc).strftime('%b %d, %Y · %H:%M UTC').upper()


def watermark(d, source, color=DIM, y=1302):
    d.text((56, y), 'Every chart hides a story', font=F(MED, 20), fill=MUT, anchor='lm')
    d.text((W - 56, y), f'Source: {source}' if source else 'Chain Secrets', font=F(MED, 17), fill=color, anchor='rm')


# ------------------------------------------------------------ 1. BREAKING RED
def breaking(title, keyfact='', source='', tag='BREAKING'):
    im = Image.new('RGB', (W, H), (10, 10, 14)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 250], fill=(214, 30, 48))
    for i in range(-2, 14):                                           # diagonal hazard stripes under the banner
        d.polygon([(i * 90, 250), (i * 90 + 45, 250), (i * 90 + 75, 285), (i * 90 + 30, 285)], fill=(214, 30, 48))
    d.ellipse([56, 74, 104, 122], fill=WHITE)
    d.text((126, 98), 'BREAKING NEWS', font=F(BLACK, 76), fill=WHITE, anchor='lm')
    d.text((60, 190), now_stamp(), font=F(SEMI, 24), fill=(255, 214, 218))
    lg, m = card.logo(64); im.paste(lg, (W - 56 - 64, 150), m)
    f, lines = fit_lines(d, title, lambda s: F(BLACK, s), (92, 84, 76, 68, 60, 54), W - 112, 6)
    y = 380
    for ln in lines:
        d.text((56, y), ' '.join(ln), font=f, fill=WHITE); y += int(f.size * 1.12)
    if keyfact:
        y += 22; d.rectangle([56, y, 70, y + 8], fill=(214, 30, 48)); y += 34
        for ln in wrap_lines(d, keyfact, F(MED, 36), W - 112)[:4]:
            d.text((56, y), ' '.join(ln), font=F(MED, 36), fill=(196, 201, 214)); y += 50
    d.rectangle([0, 1196, W, 1262], fill=(214, 30, 48))                 # ticker strip
    txt = '   CHAIN SECRETS  •  EVERY CHART HIDES A STORY  •  ' * 3
    d.text((20, 1229), txt, font=F(BLACK, 28), fill=WHITE, anchor='lm')
    watermark(d, source)
    return png(im)


# ------------------------------------------------------------ 2. CASE FILE (noir)
def casefile(title, keyfact='', source='', tag='TRUE STORY'):
    n = int(hashlib.md5(title.encode()).hexdigest()[:4], 16) % 9000 + 1000
    im = Image.new('RGB', (W, H), (24, 22, 20)); d = ImageDraw.Draw(im)
    for yy in range(0, H, 6):                                           # faint scan lines
        d.line([0, yy, W, yy], fill=(28, 26, 24))
    d.rounded_rectangle([40, 150, W - 40, 1250], radius=18, fill=(214, 200, 168), outline=(120, 108, 84), width=4)   # the folder
    d.polygon([(40, 150), (470, 150), (502, 96), (70, 96)], fill=(190, 175, 140), outline=(120, 108, 84))             # folder tab
    d.text((110, 124), f'CASE FILE  No. {n}', font=M(True, 30), fill=(60, 50, 36), anchor='lm')
    ink, red = (40, 34, 26), (176, 32, 38)
    d.text((84, 214), 'SUBJECT:', font=M(True, 26), fill=(110, 96, 70))
    f, lines = fit_lines(d, title, lambda s: M(True, s), (58, 52, 46, 42, 38), W - 168, 7)
    y = 262
    for ln in lines:
        d.text((84, y), ' '.join(ln), font=f, fill=ink); y += int(f.size * 1.3)
    y += 24
    for k in range(3):                                                  # redacted lines: the mystery, never fake text
        wdt = [760, 620, 700][k]; d.rectangle([84, y, 84 + wdt, y + 26], fill=(16, 14, 12)); y += 42
    if keyfact:
        y += 18; d.text((84, y), 'EVIDENCE:', font=M(True, 26), fill=(110, 96, 70)); y += 44
        for ln in wrap_lines(d, keyfact, M(False, 30), W - 168)[:5]:
            d.text((84, y), ' '.join(ln), font=M(False, 30), fill=ink); y += 44
    st = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(st)   # rotated stamp
    sd.rounded_rectangle([560, 960, 1000, 1070], radius=10, outline=red + (230,), width=8)
    sd.text((780, 1015), 'CLASSIFIED', font=M(True, 52), fill=red + (230,), anchor='mm')
    st = st.rotate(9, center=(780, 1015), resample=Image.BICUBIC); im.paste(st, (0, 0), st)
    d.text((84, 1196), 'FILED BY  CHAIN SECRETS  ·  @thechainsecrets', font=M(True, 22), fill=(110, 96, 70), anchor='lm')
    d.text((W - 56, 1302), f'Source: {source}' if source else 'Chain Secrets', font=F(MED, 17), fill=DIM, anchor='rm')
    d.text((56, 1302), now_stamp(), font=F(MED, 17), fill=DIM, anchor='lm')
    return png(im)


# ------------------------------------------------------------ 3. POST CARD
def postcard(title, keyfact='', source='', tag='BREAKING'):
    im = card.canvas((77, 132, 255), (0.0, 0.0, 1.0, 0.6), .14); d = ImageDraw.Draw(im)
    f, lines = fit_lines(d, title, lambda s: F(BLACK, s), (70, 64, 58, 52, 48, 44), W - 200, 7)
    body_h = len(lines) * int(f.size * 1.2) + (min(4, len(wrap_lines(d, keyfact, F(MED, 34), W - 200))) * 50 + 30 if keyfact else 0)
    hh = min(190 + body_h + 150, 980); top = max(220, (H - hh) // 2 - 20); bot = top + hh
    d.rounded_rectangle([40, top, W - 40, bot], radius=40, fill=(21, 26, 38), outline=(46, 54, 74), width=3)
    lg, m = card.logo(92); im.paste(lg, (84, top + 44), m); d = ImageDraw.Draw(im)
    d.text((200, top + 62), 'Chain Secrets', font=F(BLACK, 38), fill=WHITE)
    d.text((200, top + 110), '@thechainsecrets', font=F(MED, 26), fill=MUT)
    y = top + 190
    for ln in lines:
        d.text((84, y), ' '.join(ln), font=f, fill=WHITE); y += int(f.size * 1.2)
    if keyfact:
        y += 26
        for ln in wrap_lines(d, keyfact, F(MED, 34), W - 200)[:4]:
            d.text((84, y), ' '.join(ln), font=F(MED, 34), fill=(176, 184, 202)); y += 50
    d.line([84, bot - 92, W - 84, bot - 92], fill=(46, 54, 74), width=2)
    d.text((84, bot - 52), now_stamp(), font=F(SEMI, 22), fill=MUT, anchor='lm')
    d.text((W - 84, bot - 52), f'Source: {source}'[:46] if source else 'chainsecrets', font=F(MED, 22), fill=DIM, anchor='rm')
    d.text((W // 2, top - 50), 'THE STORY', font=F(BLACK, 30), fill=(120, 140, 200), anchor='mm')
    watermark(d, '')
    return png(im)


# ------------------------------------------------------------ 4. GLASS DARK
def glass(title, keyfact='', source='', tag='BREAKING'):
    bg = Image.new('RGB', (W, H), (8, 9, 16)); g = ImageDraw.Draw(bg)
    for box, col in (((-200, 100, 640, 900), (88, 60, 255)), ((420, 500, 1300, 1300), (20, 190, 200)), ((300, -250, 1100, 420), (255, 70, 150))):
        g.ellipse(box, fill=col)
    bg = bg.filter(ImageFilter.GaussianBlur(160)); bg = Image.blend(bg, Image.new('RGB', (W, H), (8, 9, 16)), .45)
    f, lines = fit_lines(ImageDraw.Draw(bg), title, lambda s: F(BLACK, s), (84, 76, 68, 62, 56, 50), W - 112 - 100, 7)
    need = 70 + len(lines) * int(f.size * 1.14) + (30 + 42 + min(5, len(wrap_lines(ImageDraw.Draw(bg), keyfact, F(MED, 36), W - 212))) * 52 if keyfact else 0) + 60
    hgt = min(960, max(620, need)); y0 = 220 + (960 - hgt) // 3
    box = (56, y0, W - 56, y0 + hgt)
    blur = bg.crop(box).filter(ImageFilter.GaussianBlur(28))
    pan = Image.new('RGBA', (box[2] - box[0], box[3] - box[1]), (255, 255, 255, 30))
    blur = blur.convert('RGBA'); blur.alpha_composite(pan)
    mask = Image.new('L', blur.size, 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, blur.size[0] - 1, blur.size[1] - 1], radius=48, fill=255)
    bg.paste(blur.convert('RGB'), box[:2], mask); d = ImageDraw.Draw(bg)
    d.rounded_rectangle(box, radius=48, outline=(255, 255, 255, 70) if False else (120, 124, 150), width=2)
    lg, m = card.logo(64); bg.paste(lg, (56, 64), m); d = ImageDraw.Draw(bg)
    d.text((136, 82), 'CHAIN SECRETS', font=F(BLACK, 30), fill=WHITE); d.text((137, 118), now_stamp(), font=F(MED, 18), fill=(170, 176, 200))
    chip = (tag or 'BREAKING').upper(); cw = d.textlength(chip, font=F(BLACK, 22)) + 40
    d.rounded_rectangle([W - 56 - cw, 70, W - 56, 114], radius=22, fill=(255, 255, 255)); d.text((W - 56 - cw / 2, 92), chip, font=F(BLACK, 22), fill=(20, 20, 40), anchor='mm')
    y = box[1] + 70
    for ln in lines:
        d.text((box[0] + 50, y), ' '.join(ln), font=f, fill=WHITE); y += int(f.size * 1.14)
    if keyfact:
        y += 30; d.rounded_rectangle([box[0] + 50, y, box[0] + 130, y + 8], radius=4, fill=(120, 220, 230)); y += 42
        for ln in wrap_lines(d, keyfact, F(MED, 36), box[2] - box[0] - 100)[:5]:
            d.text((box[0] + 50, y), ' '.join(ln), font=F(MED, 36), fill=(206, 212, 232)); y += 52
    watermark(d, source)
    return png(bg)


# ------------------------------------------------------------ 5. NEON TERMINAL
def terminal(title, keyfact='', source='', tag='HACK'):
    G, C = (60, 255, 140), (80, 220, 255)
    im = Image.new('RGB', (W, H), (4, 8, 6)); d = ImageDraw.Draw(im)
    for yy in range(0, H, 5):
        d.line([0, yy, W, yy], fill=(6, 12, 9))
    tf, tl = fit_lines(d, title, lambda s: M(True, s), (50, 46, 42, 38, 34), W - 152, 8)
    need = 110 + 46 + 66 + len(tl) * int(tf.size * 1.34) + (30 + 46 + min(5, len(wrap_lines(d, keyfact, M(False, 30), W - 152))) * 44 if keyfact else 0) + 130
    bot = 150 + min(1080, max(640, need))
    d.rounded_rectangle([40, 150, W - 40, bot], radius=22, fill=(7, 14, 11), outline=(30, 90, 60), width=3)
    d.rounded_rectangle([40, 150, W - 40, 214], radius=22, fill=(14, 30, 22))
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse([72 + i * 44, 170, 96 + i * 44, 194], fill=c)
    d.text((W // 2, 182), 'chain-secrets — investigation', font=M(False, 22), fill=(110, 170, 140), anchor='mm')
    y = 260
    d.text((76, y), '$ open --story', font=M(True, 30), fill=G); y += 46
    d.text((76, y), '> loading the story...', font=M(False, 28), fill=C); y += 66
    f, lines = fit_lines(d, title, lambda s: M(True, s), (50, 46, 42, 38, 34), W - 152, 8)
    for ln in lines:
        d.text((76, y), ' '.join(ln), font=f, fill=(230, 255, 240)); y += int(f.size * 1.34)
    if keyfact:
        y += 30; d.text((76, y), '> detail:', font=M(True, 28), fill=C); y += 46
        for ln in wrap_lines(d, keyfact, M(False, 30), W - 152)[:5]:
            d.text((76, y), ' '.join(ln), font=M(False, 30), fill=(150, 220, 180)); y += 44
    y += 40; d.text((76, y), '$ ', font=M(True, 30), fill=G); d.rectangle([112, y + 2, 134, y + 36], fill=G)      # cursor
    d.text((56, 1302), now_stamp(), font=M(False, 18), fill=(60, 120, 90), anchor='lm')
    d.text((W - 56, 1302), f'src: {source}'[:50] if source else '@thechainsecrets', font=M(False, 18), fill=(60, 120, 90), anchor='rm')
    return png(im)


LOOKS = {'BREAKING': breaking, 'CASEFILE': casefile, 'POSTCARD': postcard, 'GLASS': glass, 'TERMINAL': terminal}
LABELS = [('🔴 Breaking', 'BREAKING'), ('🕵️ Case file', 'CASEFILE'), ('📱 Post card', 'POSTCARD'), ('🫧 Glass', 'GLASS'), ('💻 Terminal', 'TERMINAL')]
