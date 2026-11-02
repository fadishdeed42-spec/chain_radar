"""Snap an existing words .srt to the voice (fixes words that start inside the silence before them).
python3 studio/refine_srt.py JOBDIR   (rewrites JOBDIR/voicep_words.srt, keeps a .bak)"""
import sys, os, shutil, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align import refine_words, ts
d = sys.argv[1]
audio, sr = sf.read(f'{d}/voicep.wav', dtype='float32')
if audio.ndim > 1: audio = audio.mean(1)
blocks = open(f'{d}/voicep_words.srt').read().strip().split('\n\n')
f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + float(x[6:].replace(',', '.'))
wt, words = [], []
for b in blocks:
    l = b.split('\n'); a, c = l[1].split(' --> '); wt.append((f(a), f(c))); words.append(' '.join(l[2:]))
new = refine_words(audio, sr, wt)
moved = sum(1 for x, y in zip(wt, new) if abs(x[0] - y[0]) > .1)
shutil.copy(f'{d}/voicep_words.srt', f'{d}/voicep_words.srt.bak')
open(f'{d}/voicep_words.srt', 'w').write('\n'.join(f'{i+1}\n{ts(a)} --> {ts(b)}\n{w}\n' for i, ((a, b), w) in enumerate(zip(new, words))))
print(f'{d}: {moved} word starts moved by >0.1 s')
