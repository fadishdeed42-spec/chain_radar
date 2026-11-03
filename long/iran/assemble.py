"""Build timeline.json (+ the full voice wav) from the chapter voice chunks.
python3 assemble.py fake          -> timing from words at 2.6 w/s (layout tests, no audio)
python3 assemble.py real VOICEDIR -> joins cNp.wav, shifts cNp_words.srt, maps words to lines"""
import json, sys, os, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import spec
LEAD = .6

def srt(path):
    out = []
    for blk in open(path).read().strip().split('\n\n'):
        ls = blk.strip().split('\n')
        if len(ls) < 3: continue
        a, b = ls[1].split(' --> ')
        f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + float(x[6:].replace(',', '.'))
        out.append((f(a), f(b), ' '.join(ls[2:])))
    return out

def fake():
    t = LEAD; scenes = []; last_c = None
    for i, x in enumerate(spec.L):
        if last_c is not None and x['c'] != last_c: t += spec.CHAPTER_GAP
        ws = []
        for w in x['t'].split():
            d = .38 + .02 * len(w); ws.append([w, round(t, 3), round(t + d * .85, 3)]); t += d
        scenes.append({'i': i, 'c': x['c'], 't': x['t'], 'a': ws[0][1], 'b': ws[-1][2], 'words': ws, 'v': x['v']})
        t += x['g']; last_c = x['c']
    return {'dur': round(t + 1.5, 3), 'scenes': scenes}

def real(vd):
    import soundfile as sf
    parts = []; scenes = []; t = LEAD; sr = None; gi = 0
    for c in spec.CHUNKS:
        w, sr = sf.read(f'{vd}/c{c}p.wav', dtype='float32')
        if w.ndim > 1: w = w.mean(1)
        if not parts: parts.append(np.zeros(int(LEAD * sr), np.float32))
        lines = [x for x in spec.L if x['c'] == c]
        cues = srt(f'{vd}/c{c}.srt'); words = srt(f'{vd}/c{c}p_words.srt')
        assert len(cues) == len(lines), (c, len(cues), len(lines))
        for k, (x, (ca, cb, _)) in enumerate(zip(lines, cues)):
            nxt = cues[k + 1][0] if k + 1 < len(cues) else 1e9
            ws = [[tx, round(a + t, 3), round(b + t, 3)] for a, b, tx in words if ca - .05 <= a < nxt - .05]
            scenes.append({'i': gi, 'c': c, 't': x['t'], 'a': round(ca + t, 3), 'b': round(cb + t, 3), 'words': ws, 'v': x['v']}); gi += 1
        parts.append(w); t += len(w) / sr
        if c != spec.CHUNKS[-1]:
            parts.append(np.zeros(int(spec.CHAPTER_GAP * sr), np.float32)); t += spec.CHAPTER_GAP
    parts.append(np.zeros(int(1.6 * sr), np.float32)); t += 1.6
    audio = np.concatenate(parts)
    sf.write(f'{HERE}/voice_full.wav', audio, sr)
    return {'dur': round(len(audio) / sr, 3), 'scenes': scenes}

if __name__ == '__main__':
    tl = fake() if sys.argv[1] == 'fake' else real(sys.argv[2])
    out = f'{HERE}/timeline{"_fake" if sys.argv[1] == "fake" else ""}.json'
    json.dump(tl, open(out, 'w'), indent=0)
    print(out, tl['dur'], len(tl['scenes']))
