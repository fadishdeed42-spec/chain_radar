"""Studio visual looks: free cv2 filters applied to footage/photos (no GPU, no paid API).
apply(look, img, t) takes a float32 RGB image (0..255) and returns the same shape.
Looks: none, noir, comic, cartoon, lowpoly, miniature, cinematic, clay, motion (2D motion graphics).
"""
import cv2
import numpy as np

LOOKS = {
    'none': 'Original',
    'cinematic': 'Cinematic',
    'noir': 'Dark Noir',
    'comic': 'Comic-Book',
    'cartoon': '2D Cartoon',
    'lowpoly': 'Low-Poly',
    'miniature': '3D Miniature',
    'clay': 'Claymation',
    'motion': '2D Motion Graphics',
}
STOP_FPS = {'clay': 12, 'comic': 12}      # stop-motion feel: the filter is held and re-jittered at this rate

_c = {}


def _u8(im):
    return np.clip(im, 0, 255).astype(np.uint8)


def _grain(shape, t, amp, fps=24):
    k = int(t * fps) % 6
    if ('g', k, shape[:2]) not in _c:
        _c[('g', k, shape[:2])] = np.random.default_rng(k).normal(0, 1, shape[:2]).astype(np.float32)
    return _c[('g', k, shape[:2])][..., None] * amp


def _vig(h, w, strength=.55):
    if ('v', h, w, strength) not in _c:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / w) ** 2 + ((yy - h / 2) / h) ** 2)
        _c[('v', h, w, strength)] = np.clip(1 - (d - .2) * strength * 2, .3, 1)[..., None].astype(np.float32)
    return _c[('v', h, w, strength)]


def _small(im, f=4):
    h, w = im.shape[:2]
    return cv2.resize(im, (w // f, h // f), interpolation=cv2.INTER_AREA)


def _up(im, h, w):
    return cv2.resize(im, (w, h), interpolation=cv2.INTER_LINEAR)


def _edges(gray_u8, lo=60, hi=140):
    e = cv2.Canny(cv2.GaussianBlur(gray_u8, (0, 0), 1.6), lo, hi)
    return cv2.dilate(e, np.ones((3, 3), np.uint8))


def _posterize(im, n):
    q = 255.0 / n
    return np.round(im / q) * q


def _smooth(im):
    """bilateral on a quarter-size copy: cheap painterly flat-colour look"""
    h, w = im.shape[:2]
    s = _small(_u8(im), 3)
    for _ in range(2):
        s = cv2.bilateralFilter(s, 7, 40, 7)
    return _up(s.astype(np.float32), h, w)


def noir(im, t):
    g = cv2.cvtColor(_u8(im), cv2.COLOR_RGB2GRAY).astype(np.float32)
    g = np.clip((g - 118) * 1.4 + 150, 0, 255)                       # hard contrast, crushed blacks
    g = g * _vig(*g.shape, .6)[..., 0]
    out = np.stack([g * 1.02, g * 1.0, g * .92], -1)                # faint warm-silver tone
    h, w = g.shape
    # light slats across the frame (venetian-blind shadow) drifting slowly
    yy = np.arange(h, dtype=np.float32)[:, None]
    slat = .82 + .18 * (np.sin((yy + t * 18) / (h / 34)) > -.2)
    out *= slat[..., None]
    return out + _grain(out.shape, t, 5)


def comic(im, t):
    h, w = im.shape[:2]
    base = _posterize(_smooth(im), 4) * 1.12
    hsv = cv2.cvtColor(_u8(base), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.35, 0, 255)
    base = cv2.cvtColor(_u8(hsv), cv2.COLOR_HSV2RGB).astype(np.float32)
    g = cv2.cvtColor(_u8(im), cv2.COLOR_RGB2GRAY)
    # halftone dots in the shadows
    if ('ht', h, w) not in _c:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        s = max(7, w // 90)
        u, v = (xx + yy) / 1.414, (xx - yy) / 1.414
        _c[('ht', h, w)] = (np.cos(2 * np.pi * u / s) * np.cos(2 * np.pi * v / s) * .5 + .5)
    ht = _c[('ht', h, w)]
    dark = 1 - g.astype(np.float32) / 255
    dots = (ht < (dark - .35) * 1.6).astype(np.float32)
    base *= (1 - .45 * dots)[..., None]
    e = _edges(g)
    base[e > 0] = (12, 10, 16)
    return base


def cartoon(im, t):
    h, w = im.shape[:2]
    base = _posterize(_smooth(im), 7)
    hsv = cv2.cvtColor(_u8(base), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.25, 0, 255); hsv[..., 2] = np.clip(hsv[..., 2] * 1.1 + 8, 0, 255)
    base = cv2.cvtColor(_u8(hsv), cv2.COLOR_HSV2RGB).astype(np.float32)
    e = _edges(cv2.cvtColor(_u8(im), cv2.COLOR_RGB2GRAY), 50, 120)
    e = cv2.GaussianBlur(e.astype(np.float32), (0, 0), .8) / 255
    return base * (1 - e[..., None] * .9) + 0


def lowpoly(im, t):
    h, w = im.shape[:2]
    key = ('lp', h, w)
    if key not in _c:
        rng = np.random.default_rng(3)
        n = 420
        pts = np.vstack([rng.uniform(0, 1, (n, 2)) * [w, h],
                         [[0, 0], [w, 0], [0, h], [w, h]],
                         [[x, 0] for x in np.linspace(0, w, 9)], [[x, h] for x in np.linspace(0, w, 9)],
                         [[0, y] for y in np.linspace(0, h, 14)], [[w, y] for y in np.linspace(0, h, 14)]]).astype(np.float32)
        sub = cv2.Subdiv2D((0, 0, w + 1, h + 1))
        for p in pts:
            sub.insert((float(min(max(p[0], 0), w)), float(min(max(p[1], 0), h))))
        tris = sub.getTriangleList().reshape(-1, 3, 2)
        tris = [tr for tr in tris if (tr >= -1).all() and (tr[:, 0] <= w + 1).all() and (tr[:, 1] <= h + 1).all()]
        # label map: each pixel -> triangle id (so colour = mean over triangle, vectorised)
        lab = np.zeros((h, w), np.int32)
        for k, tr in enumerate(tris):
            cv2.fillConvexPoly(lab, tr.astype(np.int32), k + 1)
        _c[key] = (lab, len(tris) + 1)
    lab, n = _c[key]
    flat = lab.ravel()
    out = np.zeros_like(im)
    cnt = np.bincount(flat, minlength=n).astype(np.float32) + 1e-6
    for ch in range(3):
        out[..., ch] = (np.bincount(flat, weights=im[..., ch].ravel(), minlength=n) / cnt)[lab]
    out = out * 1.1
    shade = (((lab.astype(np.int64) * 2654435761) % 1000) / 1000.0 - .5) * 26                # slight per-facet shading
    out += shade[..., None]
    return out


def miniature(im, t):
    """tilt-shift: sharp band across the middle, strong blur top/bottom, punchy saturation"""
    h, w = im.shape[:2]
    if ('ts', h) not in _c:
        y = np.linspace(0, 1, h, dtype=np.float32)
        _c[('ts', h)] = np.clip(np.abs(y - .55) / .3 - .25, 0, 1)[:, None, None]
    m = _c[('ts', h)]
    b1 = cv2.GaussianBlur(im, (0, 0), 5); b2 = cv2.GaussianBlur(im, (0, 0), 14)

    k = np.clip(m * 2, 0, 1)
    soft = b1 * (1 - np.clip(m * 2 - 1, 0, 1)) + b2 * np.clip(m * 2 - 1, 0, 1)
    out = im * (1 - k) + soft * k
    hsv = cv2.cvtColor(_u8(out), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.5, 0, 255); hsv[..., 2] = np.clip(hsv[..., 2] * 1.12, 0, 255)
    return cv2.cvtColor(_u8(hsv), cv2.COLOR_HSV2RGB).astype(np.float32)


def cinematic(im, t):
    h, w = im.shape[:2]
    g = cv2.cvtColor(_u8(im), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    sh = np.array([-.05, .03, .09], np.float32) * 255                # teal shadows
    hi = np.array([.10, .03, -.08], np.float32) * 255                 # orange highlights
    out = im + sh * (1 - g)[..., None] + hi * g[..., None]
    out = (out - 128) * 1.12 + 124
    bl = cv2.GaussianBlur(np.clip(out - 170, 0, 255), (0, 0), 14)       # highlight bloom
    out = out + bl * .55
    out *= _vig(h, w, .7)
    bar = int(h * .1)
    out[:bar] *= .0; out[h - bar:] *= .0                                # letterbox
    return out + _grain(out.shape, t, 3.5)


def clay(im, t):
    h, w = im.shape[:2]
    base = _smooth(im)
    base = _posterize(base, 9)
    k = int(t * STOP_FPS['clay'])
    key = ('clay', h, w)
    if key not in _c:
        rng = np.random.default_rng(11)
        n = cv2.GaussianBlur(rng.normal(0, 1, (h // 3, w // 3)).astype(np.float32), (0, 0), 1.2)
        _c[key] = cv2.resize(n, (w, h))
    tex = _c[key]
    # fingerprint-ish bumpy lighting, shifted every stop-motion frame
    dx, dy = (k * 7) % 11 - 5, (k * 5) % 9 - 4
    tex = np.roll(tex, (dy, dx), (0, 1))
    gx = cv2.Sobel(tex, cv2.CV_32F, 1, 0); gy = cv2.Sobel(tex, cv2.CV_32F, 0, 1)
    light = (gx * .7 + gy * .7) * 22
    base = base * 1.08 + light[..., None]
    hsv = cv2.cvtColor(_u8(base), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.2, 0, 255)
    base = cv2.cvtColor(_u8(hsv), cv2.COLOR_HSV2RGB).astype(np.float32)
    # slightly wobbly outline like squished clay
    g = cv2.cvtColor(_u8(im), cv2.COLOR_RGB2GRAY)
    e = cv2.GaussianBlur(_edges(g, 40, 100).astype(np.float32), (0, 0), 2.2) / 255
    return base * (1 - e[..., None] * .55)


def motion(im, t):
    """2D motion-graphics: footage becomes a dark duotone plate with a subtle moving grid"""
    h, w = im.shape[:2]
    g = cv2.cvtColor(_u8(im), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    g = np.clip((g - .15) * 1.4, 0, 1)
    dark = np.array([10, 12, 28], np.float32); light = np.array([70, 110, 255], np.float32)
    out = dark + (light - dark) * g[..., None]
    s = max(48, w // 12)
    yy, xx = np.mgrid[0:h, 0:w]
    gx = ((xx + t * 20) % s) < 2; gy = ((yy + t * 12) % s) < 2
    out = out + (gx | gy)[..., None] * np.array([18, 26, 50], np.float32)
    return out


_FN = {'noir': noir, 'comic': comic, 'cartoon': cartoon, 'lowpoly': lowpoly, 'miniature': miniature,
       'cinematic': cinematic, 'clay': clay, 'motion': motion}


def apply(look, im, t, scale=3):
    """Run a look on a (cheaper) downscaled copy and upscale -- keeps 1440p renders fast."""
    fn = _FN.get(look)
    if fn is None or im is None:
        return im
    h, w = im.shape[:2]
    f = scale
    s = cv2.resize(im, (w // f, h // f), interpolation=cv2.INTER_AREA)
    if look in STOP_FPS:
        t = int(t * STOP_FPS[look]) / STOP_FPS[look]
    o = fn(s.astype(np.float32), t)
    return cv2.resize(np.clip(o, 0, 255), (w, h), interpolation=cv2.INTER_CUBIC)


if __name__ == '__main__':
    import sys
    from PIL import Image, ImageDraw
    # synthetic test "photo": sky, sun, skyline, street
    W, H = 540, 960
    im = Image.new('RGB', (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H; d.line([(0, y), (W, y)], fill=(int(40 + 190 * k), int(70 + 110 * k), int(150 - 40 * k)))
    d.ellipse([360, 150, 460, 250], fill=(255, 220, 140))
    rng = np.random.default_rng(1)
    x = 0
    while x < W:
        bw = int(rng.integers(40, 90)); bh = int(rng.integers(250, 560))
        c = int(rng.integers(30, 90)); d.rectangle([x, H - bh - 160, x + bw, H - 160], fill=(c, c, c + 15))
        for wy in range(H - bh - 140, H - 180, 28):
            for wx in range(x + 8, x + bw - 8, 18):
                if rng.random() > .5: d.rectangle([wx, wy, wx + 8, wy + 14], fill=(255, 210, 120))
        x += bw
    d.rectangle([0, H - 160, W, H], fill=(60, 60, 66))
    d.ellipse([200, 600, 320, 760], fill=(200, 150, 120))
    arr = np.array(im).astype(np.float32)
    names = sys.argv[1:] or list(_FN)
    tiles = [im.resize((270, 480))]
    for n in names:
        tiles.append(Image.fromarray(_u8(apply(n, arr, 1.0, 1)).astype(np.uint8)).resize((270, 480)))
    sheet = Image.new('RGB', (270 * len(tiles), 480))
    dd = ImageDraw.Draw(sheet)
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * 270, 0)); dd.text((i * 270 + 6, 6), (['orig'] + names)[i], fill=(255, 255, 0))
    sheet.save('looks_test.png')
    print('ok')
