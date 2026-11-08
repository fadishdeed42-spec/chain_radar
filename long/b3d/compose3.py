"""silent.mp4 + voice -> final Short: captions only on key words/numbers, SFX on the beats, soft music.
python3 compose3.py SILENT VO_DIR PFX DUR OUT     (LEAD .3, beats.json next to this file)"""
import sys, os, json, re, subprocess, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, f'{H}/../../studio')
import sfx
silent, vo, PFX, DUR, out = sys.argv[1:6]; DUR = float(DUR); LEAD = .3
B = json.load(open(f'{H}/beats.json'))
def srt(p):
    o = []
    for b in open(p).read().strip().split('\n\n'):
        l = b.split('\n'); a, c = l[1].split(' --> ')
        f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + float(x[6:].replace(',', '.'))
        o.append((f(a) + LEAD, f(c) + LEAD, ' '.join(l[2:]).strip('".,!?')))
    return o
W = srt(f'{vo}/{PFX}p_words.srt')
# key phrases only (word sequences from the voice -> caption text); red = money/time, white = facts
KEY = [(('six', 'point', 'three', 'billion'), '$6.3 BILLION', 1), (('job', 'interview'), 'JOB INTERVIEW', 0),
       (('fake',), 'FAKE TOOL', 1), (('ad',), 'AN AD', 1), (('did', 'not', 'exist'), 'DID NOT EXIST', 1),
       (('october', 'twentieth'), 'OCT 20', 0), (('two', 'computers'), '2 COMPUTERS', 0), (('one', 'script'), 'ONE SCRIPT', 1),
       (('four', 'minutes'), '4 MINUTES', 1), (('twenty', 'minutes'), '~20 MINUTES', 1),
       (('two', 'point', 'eight', 'five'), '$2.85B FROZEN', 0), (('north', 'korean'), 'NORTH KOREA', 1), (('job', 'interview'), 'A JOB INTERVIEW', 1)]
low = [re.sub(r'[^a-z]', '', w[2].lower()) for w in W]
caps, i = [], 0
for seq, txt, red in KEY:
    j = i
    while j < len(low) and tuple(low[j:j + len(seq)]) != seq: j += 1
    if j >= len(low): print('caption not found:', seq); continue
    a = W[j][0]; b = max(W[j + len(seq) - 1][1] + .5, a + 1.0); caps.append((a, b, txt, red)); i = j + len(seq)
ts = lambda x: f'{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}'
ass = ['[Script Info]', 'PlayResX: 1080', 'PlayResY: 1920', '', '[V4+ Styles]',
       'Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginV',
       'Style: K,Inter Display ExtraBold,118,&H00FFFFFF,&H00000000,&H78000000,1,1,8,4,2,330', '', '[Events]', 'Format: Layer, Start, End, Style, Text']
for k, (a, b, t, red) in enumerate(caps):
    if k + 1 < len(caps): b = min(b, caps[k + 1][0] - .05)
    col = '\\c&H3C3CFF&' if red else ''
    ass.append(f'Dialogue: 0,{ts(a)},{ts(b)},K,{{\\an8\\pos(540,430)\\fscx130\\fscy130\\t(0,120,\\fscx100\\fscy100){col}}}{t}')
open('caps3.ass', 'w').write('\n'.join(ass))
# sound design on the beats
tr = np.zeros((int((DUR + 1) * sfx.SR), 2))
for t, clip in [(0.05, sfx.boom(amp=.5)), (B['june'] - .4, sfx.whoosh(amp=.25)), (B['ad'], sfx.pop(.3)), (B['downloaded'] + .1, sfx.tick(.25)),
                (B['september'] - .2, sfx.whoosh(amp=.25)), (B['exist'], sfx.glitch(amp=.3)), (B['code'], sfx.tick(.25)),
                (B['twentieth'] + .2, sfx.glitch(.6, .35)), (B['twentieth'] + .4, sfx.thud(amp=.5)), (B['script'] - 1.0, sfx.whoosh(amp=.25)),
                (B['script'] + .1, sfx.tick(.3)), (B['xrp'] - 1.6, sfx.riser(1.6, .2)), (B['xrp'], sfx.boom(amp=.45)), (B['bitcoin'], sfx.whoosh(amp=.3)),
                (B['froze'] + .2, sfx.ding(880, 1.2, .25)), (B['fbi'], sfx.thud(amp=.5)), (B['interview2'] - .6, sfx.sweep(1.0, False, .2))]:
    sfx.place(tr, clip, max(0, t))
sfx.write('sfx3.wav', tr * .7)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-itsoffset', str(LEAD), '-i', f'{vo}/{PFX}p.wav', '-stream_loop', '-1', '-i', f'{H}/../../studio/music.wav', '-i', 'sfx3.wav',
                '-filter_complex', f'[0:v]scale=1080:1920:flags=lanczos,ass=caps3.ass:fontsdir={H}/../../studio/fonts[v];[2:a]volume=0.08[m];[3:a]volume=0.8[s];[1:a]apad[vv];[vv][m][s]amix=inputs=3:duration=first:normalize=0,loudnorm=I=-14:TP=-1[a]',
                '-map', '[v]', '-map', '[a]', '-t', str(DUR), '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out], check=True)
m = subprocess.run(['ffmpeg', '-i', out, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', m)[-1])
if abs(I + 14) > .5:                                              # one-pass loudnorm can miss: correct to -14 LUFS
    os.rename(out, out + '.tmp.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', out + '.tmp.mp4', '-af', f'volume={-14 - I:.2f}dB,alimiter=limit=0.89', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out], check=True)
    os.remove(out + '.tmp.mp4')
print(out, len(caps), 'captions', 'LUFS was', I)
