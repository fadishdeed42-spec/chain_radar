"""Original procedural score for the long video ($0, no samples, no copyright claims).
Dark investigative bed in D minor; intensity follows the chapters in timeline.json.
python3 music.py timeline.json out.wav"""
import sys, json, wave
import numpy as np
SR = 48000
NOTE = lambda n: 440 * 2 ** ((n - 69) / 12)
# chord tones (MIDI) — i–VI–III–VII and a darker i–iv–VI–V
PROG_A = [[50, 57, 62, 65], [46, 53, 58, 62], [41, 53, 57, 60], [48, 55, 60, 64]]   # Dm  Bb  F  C
PROG_B = [[50, 57, 62, 65], [43, 55, 58, 62], [46, 53, 58, 62], [45, 52, 57, 61]]   # Dm  Gm  Bb  A
BPM = 72; BEAT = 60 / BPM; BAR = 4 * BEAT
INTENS = {0: 2, 1: 3, 2: 2, 3: 1, 4: 3, 5: 2, 6: 2, 7: 1, 8: 1}
DARK = {4, 5}

def voice_tone(f, n, rng):
    t = np.arange(n) / SR; out = np.zeros(n, np.float32)
    for det in (-.0035, .0035):
        ph = rng.uniform(0, 6.28)
        for k in range(1, 7):
            out += (np.sin(2 * np.pi * f * (1 + det) * k * t + ph * k) / k ** 1.6).astype(np.float32)
    return out

def main(tlp, out):
    tl = json.load(open(tlp)); dur = tl['dur']; n = int(dur * SR) + SR
    sc = tl['scenes']
    def chap(t):
        c = sc[0]['c']
        for s in sc:
            if s['a'] - .5 <= t: c = s['c']
            else: break
        return c
    rng = np.random.default_rng(11)
    mix = np.zeros(n, np.float32)
    nb = int(dur / BAR) + 2
    xf = int(.9 * SR)
    for b in range(nb):
        t0 = b * BAR; c = chap(t0); I = INTENS.get(c, 1)
        prog = PROG_B if c in DARK else PROG_A
        ch = prog[(b // 2) % 4]                                   # each chord holds two bars
        a = int(t0 * SR); m = int(BAR * SR) + xf
        if a >= n: break
        m = min(m, n - a)
        x_ = min(xf, m // 2); env = np.ones(m, np.float32); env[:x_] = np.linspace(0, 1, x_) ** .7; env[-x_:] = np.linspace(1, 0, x_) ** .7
        pad = sum(voice_tone(NOTE(x), m, rng) for x in ch[1:]) * .045
        mix[a:a + m] += pad * env
        # bass: root, long notes; pulsing quarter notes when intensity >= 2
        tt = np.arange(m) / SR; root = NOTE(ch[0] - 12)
        bass = (np.sin(2 * np.pi * root * tt) + .35 * np.sin(4 * np.pi * root * tt)).astype(np.float32)
        if I >= 2:
            pulse = np.zeros(m, np.float32)
            for q in range(8 if I >= 3 else 4):
                s0 = int(q * (BEAT if I < 3 else BEAT / 2) * SR)
                if s0 >= m: break
                L = min(m - s0, int(.45 * SR)); pulse[s0:s0 + L] += np.exp(-np.arange(L) / SR * 6) * np.minimum(1, np.arange(L) / (.012 * SR))
            bass *= .25 + .75 * pulse
        mix[a:a + m] += bass * env * .09
        # heartbeat thump in the darkest chapters
        if c in DARK:
            for q in range(4):
                s0 = a + int(q * BEAT * SR)
                for off, g in ((0, 1), (int(.22 * SR), .6)):
                    L = int(.25 * SR)
                    if s0 + off + L < n:
                        e = np.exp(-np.arange(L) / SR * 18) * np.minimum(1, np.arange(L) / (.004 * SR))
                        mix[s0 + off:s0 + off + L] += (np.sin(2 * np.pi * 52 * np.arange(L) / SR) * e * .16 * g).astype(np.float32)
        # soft clock tick in the market-test chapter, bell arpeggio in calm chapters
        if c == 6:
            for q in range(8):
                s0 = a + int(q * BEAT / 2 * SR); L = int(.03 * SR)
                if s0 + L < n: mix[s0:s0 + L] += (rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 220) * .02).astype(np.float32)
        if c in (0, 3, 7, 8) and b % 2 == 0:
            for q, x in enumerate([ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 24]):
                s0 = a + int(q * BEAT * SR); L = int(1.6 * SR)
                if s0 + L < n:
                    tq = np.arange(L) / SR
                    bell = (np.sin(2 * np.pi * NOTE(x) * tq) + .3 * np.sin(2 * np.pi * NOTE(x) * 2.01 * tq)) * np.exp(-tq * 2.6)
                    mix[s0:s0 + L] += (bell * .022).astype(np.float32)
    # low-cut the mud, gentle fades, stereo by a small delay
    mix = mix[:int(dur * SR)]
    fi = int(2 * SR); mix[:fi] *= np.linspace(0, 1, fi)
    mix /= max(1e-6, np.abs(mix).max()) / .8
    d = int(.011 * SR)
    st = np.stack([mix, np.concatenate([np.zeros(d, np.float32), mix[:-d]])], 1)
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype('<i2').tobytes())
    print('music', out, round(dur, 1), 's')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
