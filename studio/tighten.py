"""Apply the cut list from v8_timing.json to the raw voice -> voice_gox_tight.wav (with lead silence)."""
import json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(sys.argv[2]))
src = sys.argv[1]; out = sys.argv[3]
keep, pos = [], 0.0
for a, b in T['cuts']:
    keep.append((pos, a)); pos = b
keep.append((pos, 999))
F = .012  # tiny fade at every cut (cuts sit in pauses) so splices never click
def seg(i, a, b):
    f = f'[0:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS'
    if i: f += f',afade=t=in:d={F}'
    if b < 900: f += f',areverse,afade=t=in:d={F},areverse'
    return f + f'[k{i}];'
parts = ''.join(seg(i, a, b) for i, (a, b) in enumerate(keep))
cat = ''.join(f'[k{i}]' for i in range(len(keep)))
lead = int(T['lead'] * 1000)
fc = parts + f'{cat}concat=n={len(keep)}:v=0:a=1,aresample=48000,adelay={lead}|{lead},apad=whole_dur={T["dur"]}[a]'
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-filter_complex', fc, '-map', '[a]', '-ac', '2', '-t', str(T['dur']), out], check=True)
print('ok', out)
