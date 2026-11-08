"""Screen contents for the 3D Binance Short, one image per video frame, driven by the voice beats.
python3 ui.py beats.json DUR OUTDIR FONTDIR  ->  OUTDIR/{a,b,w}/0001.jpg ...   (a = laptop A, b = laptop B, w = wall display)"""
import sys, os, json, math
from PIL import Image, ImageDraw, ImageFont
B = json.load(open(sys.argv[1])); DUR = float(sys.argv[2]); OUT = sys.argv[3]; FD = sys.argv[4]
FPS = 30; NF = int(DUR * FPS); SW, SH = 1280, 800
_f = {}
def F(n, z):
    if (n, z) not in _f: _f[(n, z)] = ImageFont.truetype(os.path.join(FD, n), z)
    return _f[(n, z)]
BOLD, SEMI, MONO = 'InterDisplay-ExtraBold.otf', 'Inter-SemiBold.otf', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
if not os.path.exists(MONO): MONO = 'Inter-SemiBold.otf'
seg = lambda t, a, b: max(0., min(1., (t - a) / max(1e-6, b - a)))

def desktop(d, glow=(20, 40, 80)):
    d.rectangle([0, 0, SW, SH], fill=glow)
def search(d, t):
    d.rectangle([0, 0, SW, SH], fill=(246, 247, 250))
    d.rounded_rectangle([120, 50, 1160, 120], 35, fill=(255, 255, 255), outline=(200, 205, 215), width=3)
    d.text((170, 85), 'wallet signing tool download', font=F(SEMI, 34), fill=(40, 44, 52), anchor='lm')
    hi = seg(t, B['june'] + .2, B['june'] + .5)
    y = 170
    d.rounded_rectangle([110, y - 10, 1170, y + 150], 16, fill=(255, 235, 235) if hi else (255, 255, 255), outline=(230, 60, 60) if hi else (255, 255, 255), width=5)
    pz = 1 + .6 * max(0., 1 - abs(t - B['ad']) / .5)
    d.rounded_rectangle([130, y + 24 - 18 * pz, 130 + 60 * pz, y + 24 + 18 * pz], 8, fill=(220, 30, 30) if pz > 1 else (30, 30, 30)); d.text((130 + 30 * pz, y + 24), 'Ad', font=F(BOLD, int(26 * pz)), fill=(255, 255, 255), anchor='mm')
    d.text((215 + 40 * (pz - 1), y + 24), 'sponsored', font=F(SEMI, 26), fill=(110, 115, 125), anchor='lm')
    d.text((130, y + 80), 'Wallet Tool — Official Download', font=F(BOLD, 44), fill=(26, 60, 170), anchor='lm')
    d.text((130, y + 128), 'Fast. Secure. Free for developers.', font=F(SEMI, 28), fill=(80, 85, 95), anchor='lm')
    for k in range(3):
        yy = 390 + k * 130
        d.text((130, yy), 'Wallet Tool — Docs and releases', font=F(BOLD, 38), fill=(26, 60, 170), anchor='lm')
        d.rectangle([130, yy + 35, 1000 - k * 120, yy + 55], fill=(225, 228, 235))
    p = seg(t, B['downloaded'], B['downloaded'] + 1.4)
    if 0 < p and t < B['downloaded'] + 2.6:
        d.rounded_rectangle([200, 600, 1080, 760], 20, fill=(30, 32, 40))
        d.text((240, 640), 'Downloading  wallet-tool.zip', font=F(SEMI, 34), fill=(255, 255, 255), anchor='lm')
        d.rounded_rectangle([240, 690, 1040, 720], 15, fill=(70, 74, 86)); d.rounded_rectangle([240, 690, 240 + 800 * p, 720], 15, fill=(80, 200, 120))
def infected(d, t, t0, label):
    u = seg(t, t0, t0 + .5)
    if u <= 0 or t > B['interview2'] - 1.2: return
    ov = Image.new('RGBA', (SW, SH), (200, 20, 20, int(150 * u))); d._image.paste(Image.alpha_composite(d._image.convert('RGBA'), ov).convert('RGB'))
    d.rectangle([0, SH / 2 - 95, SW, SH / 2 + 95], fill=(20, 4, 6))
    d.text((SW / 2, SH / 2), label, font=F(BOLD, 110), fill=(255, 255, 255), anchor='mm')
def call(d, t):
    d.rectangle([0, 0, SW, SH], fill=(18, 20, 28))
    d.rectangle([0, 0, SW, 70], fill=(30, 33, 45)); d.text((40, 35), 'Job interview  ·  video call', font=F(SEMI, 32), fill=(230, 232, 240), anchor='lm')
    d.ellipse([1180, 22, 1206, 48], fill=(230, 60, 60)); d.text((1170, 35), 'REC', font=F(SEMI, 24), fill=(230, 60, 60), anchor='rm')
    back = t > B['interview2'] - 1.2                                      # the ending goes back to the interview
    gone = 0. if back else seg(t, B['exist'], B['exist'] + .5)
    d.rounded_rectangle([60, 100, 1220, 700], 20, fill=(40, 46, 62))
    if gone < 1:
        a = int(255 * (1 - gone))
        lay = Image.new('RGBA', (SW, SH), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
        ld.ellipse([540, 210, 740, 410], fill=(12, 12, 16, a)); ld.rounded_rectangle([450, 400, 830, 700], 120, fill=(12, 12, 16, a))
        ld.text((640, 650), 'CEO', font=F(BOLD, 40), fill=(255, 255, 255, a), anchor='mm')
        d._image.paste(Image.alpha_composite(d._image.convert('RGBA'), lay).convert('RGB'))
        if gone > 0:                                                             # glitch bands while he vanishes
            for k in range(6): d.rectangle([60, 100 + k * 100 + int(30 * math.sin(t * 40 + k)), 1220, 130 + k * 100], fill=(200, 30, 60))
    if gone >= .5: d.text((640, 400), 'THIS COMPANY DOES NOT EXIST', font=F(BOLD, 58), fill=(255, 80, 80), anchor='mm')
    d.rounded_rectangle([1000, 560, 1200, 690], 14, fill=(70, 80, 100)); d.text((1100, 625), 'you', font=F(SEMI, 28), fill=(220, 225, 235), anchor='mm')
    p = seg(t, B['code'], B['code'] + 1.2)
    if 0 < p and t < B['code'] + 2.4 and not back:
        d.rounded_rectangle([200, 600, 1080, 760], 20, fill=(10, 12, 16))
        d.text((240, 640), 'Downloading  test-project', font=F(SEMI, 34), fill=(255, 255, 255), anchor='lm')
        d.rounded_rectangle([240, 690, 1040, 720], 15, fill=(70, 74, 86)); d.rounded_rectangle([240, 690, 240 + 800 * p, 720], 15, fill=(80, 200, 120))
def wall(d, t):
    d.rectangle([0, 0, SW, SH], fill=(8, 10, 16))
    if t < B['script'] - .3:
        d.text((SW / 2, SH / 2 - 30), 'HOT WALLETS', font=F(BOLD, 64), fill=(120, 200, 255), anchor='mm')
        d.text((SW / 2, SH / 2 + 50), 'status: normal', font=F(MONO, 36), fill=(80, 200, 120), anchor='mm'); return
    cmd = '$ ./run_script'
    n = int(len(cmd) * seg(t, B['script'] - .3, B['script'] + .5))
    d.text((60, 70), cmd[:n] + ('_' if int(t * 3) % 2 else ''), font=F(MONO, 44), fill=(80, 255, 140), anchor='lm')
    if t < B['xrp'] - .2: return
    el = max(0., t - (B['xrp'] - .2)); mm = min(4.0, el * 4 / max(.1, B['minutes1'] - B['xrp'] + 1.0))
    d.text((SW - 60, 70), f'00:0{int(mm)}:{int((mm % 1) * 60):02d}', font=F(MONO, 44), fill=(255, 90, 90), anchor='rm')
    for i in range(5):
        y = 170 + i * 115; drain = seg(t, B['xrp'] + i * .15, B['xrp'] + 2.4 + i * .15)
        d.text((60, y), f'HOT WALLET {i + 1}', font=F(SEMI, 36), fill=(220, 225, 235), anchor='lm')
        d.rounded_rectangle([420, y - 22, 1220, y + 22], 10, fill=(40, 44, 56))
        d.rounded_rectangle([420, y - 22, 420 + 800 * (1 - drain) + 1, y + 22], 10, fill=(255, 190, 60) if drain < 1 else (120, 30, 30))
    tot = int(233_460_000 * seg(t, B['xrp'], B['xrp'] + 2.6))
    d.text((SW / 2, 760), f'{tot:,} XRP  moved', font=F(BOLD, 46), fill=(255, 90, 90), anchor='mm')

os.makedirs(OUT, exist_ok=True)
for k in 'abw': os.makedirs(f'{OUT}/{k}', exist_ok=True)
for fr in range(1, NF + 1):
    t = (fr - 1) / FPS
    for k in 'abw':
        im = Image.new('RGB', (SW, SH)); d = ImageDraw.Draw(im)
        if k == 'a':
            desktop(d) if t < B['june'] - .3 else search(d, t)
            infected(d, t, B['twentieth'] + .2, 'TAKEN OVER')
        elif k == 'b':
            desktop(d) if t < B['september'] - .3 else call(d, t)
            infected(d, t, B['twentieth'] + .35, 'TAKEN OVER')
        else:
            wall(d, t)
        im.save(f'{OUT}/{k}/{fr:04d}.jpg', quality=88)
print('ui frames', NF)
