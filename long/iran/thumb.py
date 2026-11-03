"""YouTube thumbnail 1280x720 (drawn at 2x then reduced). python3 thumb.py out.jpg [variant]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R
from PIL import Image, ImageDraw
W, H = 2560, 1440
def main(out, var='a'):
    import numpy as np
    bg = np.zeros((H, W, 3), np.float32) + np.array(R.BG)
    xx, yy = np.meshgrid(np.arange(W), np.arange(H))
    bg += (np.exp(-(((xx - 600) ** 2 + (yy - 700) ** 2) / (2 * 700 ** 2))) * .22)[:, :, None] * np.array(R.RED)
    img = Image.fromarray(np.clip(bg, 0, 255).astype('uint8')).convert('RGBA'); d = ImageDraw.Draw(img)
    # oil and bitcoin over the war, right side
    pts_b = [r['close'] for k, r in R.series('btc', '2026-02-27', '2026-11-02')]
    pts_w = [p for k, p in R.series('wti', '2026-02-27', '2026-10-27')]
    for pts, col, y0, y1 in ((pts_w, R.OIL, 820, 1300), (pts_b, R.BTC, 820, 1300)):
        lo, hi = min(pts), max(pts); n = len(pts)
        xy = [(1340 + 1140 * i / (n - 1), y1 - (y1 - y0) * (p - lo) / (hi - lo)) for i, p in enumerate(pts)]
        d.line(xy, fill=col + (255,), width=12, joint='curve')
    d.text((1340, 760), 'BITCOIN', font=R.F(R.BLACK, 70), fill=R.BTC + (255,), anchor='ls')
    d.text((1720, 760), 'OIL', font=R.F(R.BLACK, 70), fill=R.OIL + (255,), anchor='ls')
    # the number
    d.text((80, 760), '34', font=R.F(R.BLACK, 820), fill=R.RED + (255,), anchor='ls')
    d.text((110, 1000), 'TIMES', font=R.F(R.BLACK, 190), fill=R.INK + (255,), anchor='ls')
    d.text((120, 1300), '"VERY SOON"', font=R.F(R.LORA_I, 170, 'Bold Italic'), fill=R.INK + (255,), anchor='ls')
    d.text((1340, 330), 'THE IRAN WAR', font=R.F(R.BLACK, 132), fill=R.INK + (255,), anchor='ls')
    d.text((1340, 520), 'WILL END SOON?', font=R.F(R.BLACK, 132), fill=R.INK + (255,), anchor='ls')
    d.rectangle([1340, 580, 2460, 600], fill=R.RED + (255,))
    img.convert('RGB').resize((1280, 720), Image.LANCZOS).save(out, quality=94)
    print(out)
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'a')
