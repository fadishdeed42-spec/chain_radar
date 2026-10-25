"""Procedural sound effects (no samples, $0). Writes a 48kHz stereo WAV timeline."""
import numpy as np, wave, sys, json, os

SR = 48000
rng = np.random.default_rng(3)

def env(n, a=.005, r=.3, curve=4):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-curve * t / max(r, 1e-4))
    return e

def lowpass(x, cutoff):
    # one-pole lowpass, cutoff may be array
    a = np.exp(-2 * np.pi * np.asarray(cutoff) / SR) * np.ones_like(x)
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)):
        s = (1 - a[i]) * x[i] + a[i] * s; y[i] = s
    return y

def boom(d=1.4, f0=70, f1=38, amp=.9):
    n = int(d * SR); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * env(n, .002, d * .5, 3.5)
    click = rng.standard_normal(n) * env(n, .0005, .03, 30) * .5
    return amp * (body + click)

def thud(d=.5, amp=.8):
    n = int(d * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * (120 * np.exp(-t * 18) + 55) * t) * env(n, .001, .18, 6)
    noise = lowpass(rng.standard_normal(n), 1800) * env(n, .001, .06, 20)
    return amp * (s + noise * .8)

def whoosh(d=.8, up=True, amp=.5):
    n = int(d * SR); x = np.linspace(0, 1, n)
    cut = (300 + 5000 * x ** 2) if up else (5300 - 5000 * x ** .5)
    w = lowpass(rng.standard_normal(n), cut)
    shape = np.sin(np.pi * x) ** 1.5
    return amp * w * shape * 2.2

def riser(d=2.0, amp=.35):
    n = int(d * SR); t = np.arange(n) / SR; x = t / d
    f = 180 + 900 * x ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * .4 + np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * .2
    noise = lowpass(rng.standard_normal(n), 400 + 6000 * x ** 2) * .9
    return amp * (tone + noise) * x ** 1.6

def ding(f=1320, d=.9, amp=.35):
    n = int(d * SR); t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.7 for k in (1, 2, 3))
    s2 = np.roll(sum(np.sin(2 * np.pi * f * 1.5 * k * t) / k ** 1.7 for k in (1, 2)), int(.09 * SR))
    return amp * (s + s2 * .8) * env(n, .002, .35, 5)

def tick(amp=.35):
    n = int(.05 * SR)
    return amp * lowpass(rng.standard_normal(n), 6000) * env(n, .0005, .012, 40) * 2

def pop(amp=.4, f=600):
    n = int(.12 * SR); t = np.arange(n) / SR
    return amp * np.sin(2 * np.pi * (f + 900 * np.exp(-t * 60)) * t) * env(n, .001, .05, 18)

def glitch(d=.5, amp=.35):
    n = int(d * SR); out = np.zeros(n)
    pos = 0
    while pos < n:
        L = int(rng.uniform(.01, .05) * SR)
        kind = rng.integers(3)
        t = np.arange(min(L, n - pos)) / SR
        if kind == 0: seg = np.sign(np.sin(2 * np.pi * rng.uniform(200, 1400) * t))
        elif kind == 1: seg = rng.standard_normal(len(t))
        else: seg = np.zeros(len(t))
        out[pos:pos + len(t)] = seg * rng.uniform(.3, 1)
        pos += L
    return amp * out * np.sin(np.linspace(0, np.pi, n)) ** .3

def sweep(d=1.0, up=True, amp=.35):
    n = int(d * SR); x = np.linspace(0, 1, n)
    f = (200 + 1400 * x ** 2) if up else (1600 - 1400 * x ** .6)
    s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * .25 + np.sin(2 * np.pi * np.cumsum(f) / SR) * .6
    return amp * lowpass(s, 4000) * np.sin(np.pi * x) ** .6

def place(track, clip, at, pan=0.0):
    i = int(at * SR)
    if i >= len(track): return
    c = clip[:len(track) - i]
    l, r = (1 - max(0, pan)), (1 + min(0, pan))
    track[i:i + len(c), 0] += c * l
    track[i:i + len(c), 1] += c * r

def write(path, track):
    pk = np.max(np.abs(track))
    if pk > .98: track = track * .98 / pk
    data = (track * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data.tobytes())

if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    T = json.load(open(f'{here}/v4_timing.json'))
    S = [s[0] for s in T['seg']]
    track = np.zeros((int(T['dur'] * SR), 2))
    # hook
    place(track, riser(1.5, .3), 0.05)
    place(track, boom(1.6, amp=.9), 1.55)
    place(track, glitch(.45, .3), 1.55)
    # clock ticks 4:05 -> 4:11
    for k in range(7): place(track, tick(.3), S[1] + k * .17, pan=(-.3 if k % 2 else .3))
    place(track, ding(1320), S[1] + 3.6)
    place(track, whoosh(.5, True, .3), S[1] + 3.45)
    # tweet candle pump
    place(track, riser(2.0, .38), S[2] + 1.3)
    place(track, thud(.5, .6), S[2] + 3.3)
    place(track, pop(.45, 700), S[2] + 4.25)
    # chairman / fake
    place(track, whoosh(.5, True, .3), S[3] + .9)
    place(track, ding(990, .8, .25), S[3] + 1.1)
    place(track, glitch(.6, .35), S[3] + 3.0)
    place(track, thud(.6, .9), S[3] + 4.2)
    place(track, boom(1.0, 60, 35, .5), S[3] + 4.2)
    # crash
    place(track, whoosh(1.0, False, .45), S[4] + .5)
    place(track, boom(1.8, 75, 30, 1.0), S[4] + 1.6)
    place(track, pop(.4, 500), S[4] + 3.25)
    # twist
    place(track, riser(.9, .3), S[5] - .9)
    place(track, thud(.4, .5), S[5])
    place(track, whoosh(.6, True, .3), S[5] + 1.7)
    place(track, thud(.6, .85), S[5] + 3.5)
    place(track, ding(1568, 1.0, .3), S[5] + 3.55)
    # 12-day slide: descending ticks
    for k in range(13):
        place(track, pop(.18, 900 - k * 40), S[6] + .2 + k * (4.6 / 13))
    place(track, thud(.5, .6), S[6] + 4.8)
    # pumped / dumped
    place(track, sweep(.9, True, .3), 44.31)
    place(track, sweep(.9, False, .3), 45.86)
    place(track, boom(1.2, 70, 35, .6), 46.2)
    # CTA
    place(track, pop(.4, 650), S[8])
    place(track, pop(.4, 750), S[8] + .9); place(track, pop(.4, 850), S[8] + 1.05)
    write(f'{here}/v4_sfx.wav', track)
    print('sfx ok', track.shape[0] / SR)
