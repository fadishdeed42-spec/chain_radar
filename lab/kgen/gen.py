# Runs INSIDE a free Kaggle GPU notebook (2x T4): makes short AI video clips with two open models in parallel and times them.
import os, sys, subprocess, json, time
OUT = '/kaggle/working'
PROMPTS = [
 'Cinematic realistic shot, a hooded hacker typing fast on a keyboard in a dark room lit by green code on several monitors, slow push-in, moody, shallow depth of field',
 'Cinematic realistic shot, a glass skyscraper at night, red alarm lights flashing, golden coins pouring out of a broken window into the dark sky, slow camera tilt up',
 'Cinematic realistic close-up, a hand holding a smartphone in a dark room, the screen shows a red falling chart, the hand trembles, shallow depth of field',
]
W, H = 480, 832
RUN = r'''
import sys, time, json, torch
from diffusers.utils import export_to_video
which, out = sys.argv[1], sys.argv[2]; P = json.loads(sys.argv[3]); W, H = int(sys.argv[4]), int(sys.argv[5])
t0 = time.time(); res = {'model': which, 'clips': []}
try:
    if which == 'wan':
        from diffusers import AutoencoderKLWan, WanPipeline
        mid = 'Wan-AI/Wan2.1-T2V-1.3B-Diffusers'
        vae = AutoencoderKLWan.from_pretrained(mid, subfolder='vae', torch_dtype=torch.float32)
        pipe = WanPipeline.from_pretrained(mid, vae=vae, torch_dtype=torch.float16)
        kw = dict(num_frames=49, num_inference_steps=25, guidance_scale=5.0, negative_prompt='blurry, low quality, distorted, text, watermark, cartoon'); fps = 16
    else:
        from diffusers import LTXPipeline
        pipe = LTXPipeline.from_pretrained('Lightricks/LTX-Video', torch_dtype=torch.float16)
        kw = dict(num_frames=65, num_inference_steps=30, negative_prompt='worst quality, blurry, jittery, distorted, text, watermark'); fps = 24
    pipe.enable_model_cpu_offload()
    res['load_s'] = round(time.time() - t0)
    for k, p in enumerate(P):
        t1 = time.time()
        fr = pipe(prompt=p, width=W, height=H, **kw).frames[0]
        f = f'{out}/{which}_{k + 1}.mp4'; export_to_video(fr, f, fps=fps)
        res['clips'].append({'file': f, 'secs': round(time.time() - t1), 'frames': len(fr), 'fps': fps})
        print(which, k + 1, round(time.time() - t1), 's', flush=True)
except Exception as e:
    import traceback; res['error'] = traceback.format_exc()[-1500:]; print(res['error'], flush=True)
res['total_s'] = round(time.time() - t0)
json.dump(res, open(f'{out}/{which}.json', 'w'), indent=1)
'''
open('/tmp/run_one.py', 'w').write(RUN)
LOG = open(f'{OUT}/run.txt', 'a')
def sh(c):
    p = subprocess.run(c, shell=True, capture_output=True, text=True); LOG.write(f'$ {c}\n{(p.stdout + p.stderr)[-3000:]}\n'); LOG.flush(); return p.returncode
sh('nvidia-smi --query-gpu=name,memory.total --format=csv')
sh('pip install -q -U diffusers transformers accelerate sentencepiece imageio imageio-ffmpeg ftfy 2>&1 | tail -3')
procs = []
for gpu, which in ((0, 'ltx'), (1, 'wan')):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu))
    procs.append(subprocess.Popen([sys.executable, '/tmp/run_one.py', which, OUT, json.dumps(PROMPTS), str(W), str(H)], env=env,
                                  stdout=open(f'{OUT}/{which}.log', 'w'), stderr=subprocess.STDOUT))
for p in procs: p.wait()
for which in ('ltx', 'wan'):
    try: LOG.write(open(f'{OUT}/{which}.json').read() + '\n')
    except Exception as e: LOG.write(f'{which}: no result {e}\n')
    try: LOG.write(open(f'{OUT}/{which}.log').read()[-2500:] + '\n')
    except Exception: pass
LOG.close(); print(open(f'{OUT}/run.txt').read()[-6000:])
