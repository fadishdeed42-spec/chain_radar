"""parts + voice -> final 1080x1920 Short with one-word captions and a soft music bed"""
import sys, os, subprocess, glob
vo, parts, out = sys.argv[1], sys.argv[2], sys.argv[3]
def srt(p):
    o = []
    for b in open(p).read().strip().split('\n\n'):
        l = b.split('\n'); a, c = l[1].split(' --> ')
        f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + float(x[6:].replace(',', '.'))
        o.append((f(a), f(c), ' '.join(l[2:])))
    return o
LEAD = .2
w = srt(f'{vo}/b0p_words.srt')
ts = lambda x: f'{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}'
ass = ['[Script Info]', 'PlayResX: 1080', 'PlayResY: 1920', '', '[V4+ Styles]',
       'Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginV',
       'Style: W,DejaVu Sans,110,&H00FFFFFF,&H00000000,&H64000000,1,1,9,3,2,560', '', '[Events]', 'Format: Layer, Start, End, Style, Text']
for i, (a, b, t) in enumerate(w):
    nb = w[i + 1][0] if i + 1 < len(w) else b + .3
    t = t.strip('".,!?').upper()
    col = '\\c&H3C3CFF&' if any(ch.isdigit() for ch in t) or t in ('BILLION', 'GONE', 'MINUTES') else ''
    ass.append(f'Dialogue: 0,{ts(a + LEAD)},{ts(nb + LEAD)},W,{{\\fscx120\\fscy120\\t(0,90,\\fscx100\\fscy100){col}}}{t}')
open('caps.ass', 'w').write('\n'.join(ass))
ps = sorted(glob.glob(f'{parts}/part_*.mp4'))
open('parts.txt', 'w').write(''.join(f"file '{os.path.abspath(p)}'\n" for p in ps))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'parts.txt', '-c', 'copy', 'silent.mp4'], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'silent.mp4', '-itsoffset', str(LEAD), '-i', f'{vo}/b0p.wav', '-stream_loop', '-1', '-i', '../../studio/music.wav',
                '-filter_complex', '[0:v]scale=1080:1920:flags=lanczos,ass=caps.ass[v];[2:a]volume=0.10[m];[1:a]apad[vv];[vv][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1[a]',
                '-map', '[v]', '-map', '[a]', '-t', '15.2', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out], check=True)
print(out)
