"""AI-scene Short: one AI clip per voice line, cut exactly when the line starts; key-word captions; SFX; subscribe end card.
python3 make.py CLIPDIR VOICE_JSON VO_WAV VO_WORDS_SRT OUT.mp4"""
import sys, os, json, re, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
H_ = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(H_, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'studio')); import sfx
CLIPS, VJ, WAV, SRT, OUT = sys.argv[1:6]
TMP = OUT + '_tmp'; os.makedirs(TMP, exist_ok=True)
LEAD, W, H, FPS = .15, 1080, 1920, 30
FD = os.path.join(ROOT, 'studio', 'fonts')

# ---- voice lines -> start times (forced-aligned words, counted per line)
lines = [s[0] for s in json.load(open(VJ))['scenes']]
def srt(p):
    out = []
    for b in open(p).read().strip().split('\n\n'):
        l = b.split('\n'); a, c = l[1].split(' --> ')
        f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + float(x[6:].replace(',', '.'))
        out.append((f(a) + LEAD, f(c) + LEAD, ' '.join(l[2:])))
    return out
WD = srt(SRT)
counts = [len(t.split()) for t in lines]
assert sum(counts) == len(WD), f'word count mismatch: script {sum(counts)} vs aligned {len(WD)}'
starts, k = [], 0
for n in counts: starts.append(WD[k][0]); k += n
END = WD[-1][1] + 1.2
print('line starts', [round(x, 2) for x in starts], 'end', round(END, 2))

def word_t(line_i, word):                     # time of the first word in line_i that starts with `word`
    k = sum(counts[:line_i])
    for j in range(counts[line_i]):
        if re.sub(r'[^a-z0-9]', '', WD[k + j][2].lower()).startswith(word.lower()): return WD[k + j][0]
    return starts[line_i]

# ---- picture: clip i for line i (cut on the line's first word), end card for the last line
segs, n_story = [], len(lines) - 1
bounds = [0.0] + [max(0, starts[i] - .08) for i in range(1, len(lines))] + [END]
for i in range(n_story):
    d = bounds[i + 1] - bounds[i]; src = os.path.join(CLIPS, f'clip_{i + 1:02d}.mp4')
    cd = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src]))
    slow = max(1.0, d / cd)                                         # a longer line: play the clip a little slower (never freeze)
    o = f'{TMP}/s{i:02d}.mp4'
    vf = (f'setpts={slow:.4f}*PTS,fps={FPS},scale={W}:-2:flags=lanczos,crop={W}:{H},'
          f'eq=contrast=1.06:saturation=1.08,unsharp=5:5:0.6,trim=duration={d:.3f},setpts=PTS-STARTPTS')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vf', vf, '-an', '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', '-pix_fmt', 'yuv420p', o], check=True)
    segs.append(o)
# end card
im = Image.new('RGB', (W, H), (13, 17, 26)); d_ = ImageDraw.Draw(im)
logo = Image.open(os.path.join(ROOT, 'x_logo.png')).convert('RGB').resize((300, 300)); m = Image.new('L', (300, 300), 0)
ImageDraw.Draw(m).rounded_rectangle((0, 0, 299, 299), 70, fill=255); im.paste(logo, (W // 2 - 150, 640), m)
d_.text((W / 2, 1060), 'CHAIN SECRETS', font=ImageFont.truetype(f'{FD}/InterDisplay-Black.otf', 92), fill=(238, 241, 246), anchor='mm')
d_.rounded_rectangle((W / 2 - 300, 1160, W / 2 + 300, 1270), 55, fill=(230, 33, 23))
d_.text((W / 2, 1215), 'SUBSCRIBE', font=ImageFont.truetype(f'{FD}/InterDisplay-Black.otf', 56), fill=(255, 255, 255), anchor='mm')
d_.text((W / 2, 1330), 'for more true stories', font=ImageFont.truetype(f'{FD}/Inter-SemiBold.otf', 44), fill=(160, 170, 186), anchor='mm')
im.save(f'{TMP}/end.png')
o = f'{TMP}/s99.mp4'; dd = bounds[-1] - bounds[-2]
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', f'{TMP}/end.png', '-t', f'{dd:.3f}', '-vf', f'fps={FPS},zoompan=z=\'1+0.0008*on\':d=1:s={W}x{H}:fps={FPS}',
                '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', o], check=True)
segs.append(o)
open(f'{TMP}/list.txt', 'w').write(''.join(f"file '{os.path.abspath(s)}'\n" for s in segs))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{TMP}/list.txt', '-c', 'copy', f'{TMP}/pic.mp4'], check=True)

# ---- key-word captions (only what matters, on the exact word)
CAP = json.load(open(os.path.join(os.path.dirname(VJ), 'captions.json')))   # [[line, word, text, red], ...]
ts = lambda x: f'{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}'
ev = []
for li, w, txt, red in CAP:
    a = word_t(li, w); ev.append([a, txt, red])
ev.sort()
ass = ['[Script Info]', 'PlayResX: 1080', 'PlayResY: 1920', 'WrapStyle: 2', '', '[V4+ Styles]',
       'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
       'Style: K,Inter Display Black,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,8,5,8,60,60,0,1', '', '[Events]',
       'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
for j, (a, txt, red) in enumerate(ev):
    b = min(ev[j + 1][0] - .03 if j + 1 < len(ev) else bounds[-2], a + 2.2, bounds[-2])
    col = '\\c&H2F35FF&' if red else ''
    ass.append(f'Dialogue: 0,{ts(a)},{ts(b)},K,,0,0,0,,{{\\an8\\pos(540,300)\\fscx135\\fscy135\\t(0,110,\\fscx100\\fscy100){col}}}{txt}')
open(f'{TMP}/caps.ass', 'w').write('\n'.join(ass))

# ---- sound: a soft whoosh on every cut, a hit on the hook and the twist
tr = np.zeros((int((END + 1) * sfx.SR), 2))
sfx.place(tr, sfx.boom(amp=.45), 0.02)
for i in range(1, len(lines)): sfx.place(tr, sfx.whoosh(.5, amp=.16), max(0, bounds[i] - .25))
for li, w, txt, red in CAP:
    if red: sfx.place(tr, sfx.thud(amp=.35), word_t(li, w))
sfx.write(f'{TMP}/sfx.wav', tr * .8)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{TMP}/pic.mp4', '-itsoffset', str(LEAD), '-i', WAV, '-i', f'{TMP}/sfx.wav',
                '-filter_complex', f'[0:v]ass={TMP}/caps.ass:fontsdir={FD}[v];[1:a]apad[vv];[2:a]volume=0.9[s];[vv][s]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a]',
                '-map', '[v]', '-map', '[a]', '-t', f'{END:.3f}', '-r', str(FPS), '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', OUT], check=True)
m = subprocess.run(['ffmpeg', '-i', OUT, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', m)[-1])
if abs(I + 14) > .5:
    os.rename(OUT, OUT + '.tmp.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', OUT + '.tmp.mp4', '-af', f'volume={-14 - I:.2f}dB,alimiter=limit=0.84', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', OUT], check=True)
    os.remove(OUT + '.tmp.mp4')
print(OUT, 'dur', round(END, 2), 'LUFS was', I)
