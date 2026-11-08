# Runs INSIDE a free Kaggle GPU notebook: renders a Blender scene from the public repo to /kaggle/working/silent.mp4
import os, subprocess, time, json, glob
SCENE, DUR, MODE = '__SCENE__', '__DUR__', '__MODE__'
t0 = time.time()
LOG = open('/kaggle/working/run.txt', 'a')
def run(c):
    print('$', c, flush=True); LOG.write('$ ' + c + '\n')
    p = subprocess.run(c, shell=True, capture_output=True, text=True); o = (p.stdout + p.stderr)[-4000:]
    print(o, flush=True); LOG.write(o + f'\n[rc {p.returncode}]\n'); LOG.flush(); return p.returncode
run('nvidia-smi --query-gpu=name,memory.total --format=csv')
run('apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 fonts-dejavu-core ffmpeg >/dev/null 2>&1')
run('cd /kaggle/tmp 2>/dev/null || mkdir -p /kaggle/tmp; cd /kaggle/tmp && git clone -q --depth 1 https://github.com/fadishdeed42-spec/chain_radar.git repo')
run('cd /kaggle/tmp && curl -sL https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz | tar -xJ && mv blender-4.2.3-linux-x64 blender')
R = '/kaggle/tmp/repo'; D = os.path.dirname(f'{R}/{SCENE}')
run(f'python3 {D}/ui.py {D}/beats.json {DUR} /kaggle/tmp/ui {R}/studio/fonts')
nf = int(float(DUR) * 30)
t1 = time.time()
run(f'/kaggle/tmp/blender/blender -b -P {R}/{SCENE} -- {DUR} 1 {nf} /kaggle/tmp/fr /kaggle/tmp/ui {MODE} 2>&1 | grep -v "Fra:\\|Sample\\|Rendering\\|Updating" | tail -40')
secs = time.time() - t1
n = len(glob.glob('/kaggle/tmp/fr/f_*.jpg'))
run('ffmpeg -v error -y -framerate 30 -i /kaggle/tmp/fr/f_%04d.jpg -c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p /kaggle/working/silent.mp4')
run('cp /kaggle/tmp/fr/safe.json /kaggle/working/ 2>/dev/null; for t in 2 9 17 24 34 42; do ffmpeg -v error -y -ss $t -i /kaggle/working/silent.mp4 -frames:v 1 -vf scale=360:-1 /kaggle/working/still_$t.jpg; done')
json.dump({'frames': n, 'of': nf, 'render_s': round(secs), 'per_frame_s': round(secs / max(1, n), 2), 'total_s': round(time.time() - t0)}, open('/kaggle/working/timing.json', 'w'))
print(open('/kaggle/working/timing.json').read())
