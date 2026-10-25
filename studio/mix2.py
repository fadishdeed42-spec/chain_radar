"""Voice-first mix: strong ducking, linear (2-pass) loudness, and a measured voice-vs-bed check.
usage: mix2.py video voice sfx music dur out [music_vol] [sfx_vol]"""
import sys, subprocess, json, re, numpy as np, wave, os, tempfile
V, VO, FX, MU, D, OUT = sys.argv[1:7]; D = float(D)
MV = float(sys.argv[7]) if len(sys.argv) > 7 else 0.11
FV = float(sys.argv[8]) if len(sys.argv) > 8 else 0.55
tmp = tempfile.mkdtemp()
FADE = D - 1.7
G = (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,highpass=f=80,equalizer=f=3000:t=q:w=1.2:g=3.5,"
     f"acompressor=threshold=-24dB:ratio=4:attack=4:release=90:makeup=5,asplit=3[vo][sc1][sc2];"
     f"[2:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{D},volume={MV},afade=t=out:st={FADE}:d=1.7[mu];"
     f"[mu][sc1]sidechaincompress=threshold=0.015:ratio=14:attack=12:release=450:makeup=1[mud];"
     f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={FV}[fx0];"
     f"[fx0][sc2]sidechaincompress=threshold=0.012:ratio=9:attack=2:release=250[fxd];"
     f"[mud][fxd]amix=inputs=2:duration=longest:normalize=0[bed]")
def run(args): subprocess.run(['ffmpeg', '-v', 'error', '-y'] + args, check=True)
# 1) stems
run(['-i', VO, '-i', FX, '-i', MU, '-filter_complex', G, '-map', '[vo]', '-t', str(D), f'{tmp}/vo.wav',
     '-map', '[bed]', '-t', str(D), f'{tmp}/bed.wav'])
def load(p):
    with wave.open(p) as w: x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768
    return x.reshape(-1, 2).mean(1)
vo, bed = load(f'{tmp}/vo.wav'), load(f'{tmp}/bed.wav')
n = min(len(vo), len(bed)); win = int(.4 * 48000)
worst, rows = 99, []
for i in range(0, n - win, win // 2):
    rv = np.sqrt(np.mean(vo[i:i + win] ** 2)) + 1e-9; rb = np.sqrt(np.mean(bed[i:i + win] ** 2)) + 1e-9
    if 20 * np.log10(rv) > -38:                      # voice active
        d = 20 * np.log10(rv / rb); rows.append((i / 48000, d)); worst = min(worst, d)
ds = np.array([d for _, d in rows])
print(f'voice-over-bed dB while speaking: median {np.median(ds):.1f}, 5th pct {np.percentile(ds, 5):.1f}, worst {worst:.1f}')
print('worst windows:', [(round(t, 1), round(d, 1)) for t, d in sorted(rows, key=lambda r: r[1])[:5]])
# 2) mix + linear 2-pass loudnorm
mixf = f'{tmp}/mix.wav'
run(['-i', f'{tmp}/vo.wav', '-i', f'{tmp}/bed.wav', '-filter_complex',
     '[0][1]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.89:level=false[a]', '-map', '[a]', mixf])
r = subprocess.run(['ffmpeg', '-i', mixf, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                   capture_output=True, text=True).stderr
m = json.loads(r[r.rindex('{'):r.rindex('}') + 1])
ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
run(['-i', V, '-i', mixf, '-filter_complex', f'[1:a]{ln},aresample=48000[a]', '-map', '0:v', '-map', '[a]',
     '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-t', str(D), '-movflags', '+faststart', OUT])
print('mixed ->', OUT)
