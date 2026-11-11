# Runs INSIDE a free Kaggle GPU notebook (2x T4): makes short AI video clips with two open models in parallel and times them.
import os, sys, subprocess, json, time
OUT = '/kaggle/working'
PROMPTS = [  # Pizza Day Short: one 3-second scene per line, strong motion
 'Cinematic realistic close-up, two hot pizzas on a wooden table, steam rising, shiny gold coins pouring down and piling up next to them, dramatic warm light, slow push-in',
 'Cinematic realistic shot, a man at night in a small room typing on an old laptop, the screen glow lights his face, he leans in, slow push-in, 2010',
 'Cinematic realistic close-up, fingers typing fast on an old laptop keyboard at night, glowing screen, camera slowly moving sideways',
 'Cinematic realistic shot, a young college student in a dorm room at night reads his laptop screen and starts smiling, nods, slow push-in',
 'Cinematic realistic shot, a pizza delivery man walks up to a house front door at night carrying two pizza boxes, warm porch light, the door opens',
 'Cinematic realistic close-up, a man opens a pizza box on a kitchen table and lifts a cheesy slice, cheese stretching, warm light',
 'Cinematic realistic shot, a huge pile of gold coins grows taller and taller, coins falling and bouncing, glittering, dark background, camera tilts up',
 'Cinematic realistic close-up, a young man in a dark room looks up from his phone, surprised, thoughtful, slow push-in',
 'Cinematic realistic shot, a young backpacker walks fast through a bright airport terminal, planes outside the windows, tracking shot',
 'Cinematic realistic shot, a young traveler stands on a cliff at sunset looking at the ocean, wind in his hair, he smiles, slow orbit',
]
W, H = 480, 832
RUN = r'''
import os; os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
import sys, time, json, torch
from diffusers.utils import export_to_video
which, out = sys.argv[1], sys.argv[2]; P = json.loads(sys.argv[3]); W, H = int(sys.argv[4]), int(sys.argv[5])
t0 = time.time(); res = {'model': which, 'clips': []}
try:
    if which.startswith('wan'):
        import os, gc
        from diffusers import AutoencoderKLWan, WanPipeline
        mid = 'Wan-AI/Wan2.1-T2V-1.3B-Diffusers'
        vae = AutoencoderKLWan.from_pretrained(mid, subfolder='vae', torch_dtype=torch.float32)
        pipe = WanPipeline.from_pretrained(mid, vae=vae, torch_dtype=torch.float16)
        pipe.enable_model_cpu_offload()                         # the setup that worked in the test (T5 is too big to keep on the GPU)
        neg = 'blurry, low quality, distorted, static, frozen, text, watermark, cartoon'
        with torch.inference_mode():                            # no_grad: outside pipe() the encoder kept its whole graph -> OOM
            EMB = {k: pipe.encode_prompt(prompt=p + ', dynamic motion, highly detailed', negative_prompt=neg, do_classifier_free_guidance=True, max_sequence_length=226) for k, p in P.items()}
        kw = dict(num_frames=49, num_inference_steps=20, guidance_scale=5.0); fps = 16
    else:
        from diffusers import LTXPipeline
        pipe = LTXPipeline.from_pretrained('Lightricks/LTX-Video', torch_dtype=torch.float16)
        kw = dict(num_frames=65, num_inference_steps=30, negative_prompt='worst quality, blurry, jittery, distorted, text, watermark'); fps = 24
    if not which.startswith('wan'): pipe.enable_model_cpu_offload()
    res['load_s'] = round(time.time() - t0)
    for k, p in P.items():
        t1 = time.time()
        pe, ne = EMB[k]
        torch.cuda.empty_cache()
        fr = pipe(prompt_embeds=pe, negative_prompt_embeds=ne, width=W, height=H, **kw).frames[0]
        f = f'{out}/clip_{int(k) + 1:02d}.mp4'; export_to_video(fr, f, fps=fps)
        res['clips'].append({'file': f, 'secs': round(time.time() - t1), 'frames': len(fr), 'fps': fps})
        json.dump(res, open(f'{out}/{which}.json', 'w'), indent=1)
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
for gpu in (0,):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu))
    part = {i: p for i, p in enumerate(PROMPTS)}
    procs.append(subprocess.Popen([sys.executable, '/tmp/run_one.py', f'wan{gpu}', OUT, json.dumps(part), str(W), str(H)], env=env,
                                  stdout=open(f'{OUT}/wan{gpu}.log', 'w'), stderr=subprocess.STDOUT))
for p in procs: p.wait()
for which in ('wan0', 'wan1'):
    try: LOG.write(open(f'{OUT}/{which}.json').read() + '\n')
    except Exception as e: LOG.write(f'{which}: no result {e}\n')
    try: LOG.write(open(f'{OUT}/{which}.log').read()[-2500:] + '\n')
    except Exception: pass
LOG.close(); print(open(f'{OUT}/run.txt').read()[-6000:])
