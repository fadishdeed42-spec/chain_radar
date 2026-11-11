# Runs INSIDE a free Kaggle GPU notebook (2x T4): makes short AI video clips with two open models in parallel and times them.
import os, sys, subprocess, json, time
OUT = '/kaggle/working'
PROMPTS = [  # Bitcoin Faucet Short: one ~3-second scene per line
 'Cinematic realistic shot, a glowing old 2010 computer monitor in a dark bedroom shows a simple web page, golden coins burst out of the screen and fly toward the camera, magical',
 'Cinematic realistic shot, a young man in a dark room at night types on an old computer keyboard, the monitor glow on his face, slow push-in',
 'Cinematic realistic shot, five shiny gold coins drop one by one into an open hand, slow motion, sparkles, warm light, macro shot',
 'Cinematic realistic shot, a golden water faucet on a dark wall pours a stream of shiny gold coins instead of water into a sink, coins overflowing, slow motion',
 'Cinematic realistic shot, a programmer in a small 2010 home office pours a big bag of gold coins into a glass jar on his desk, coins spilling, warm lamp light',
 'Cinematic realistic shot, a mysterious hooded figure seen from behind types on a keyboard in a dark room lit by a single computer screen, green glow, slow push-in',
 'Cinematic realistic shot, a few gold coins next to a crumpled one-dollar bill on a wooden table, camera slowly orbits, soft light',
 'Cinematic realistic shot, a huge river of gold coins flows through a dark canyon, glittering, epic aerial camera move',
 'Cinematic realistic shot, a gigantic mountain of gold coins towering in a dark hall, light beams from above, camera tilts up, epic scale',
 'Cinematic realistic shot, a young man opens an old wallet app on his phone and his jaw drops in shock, face lit by the screen, slow push-in',
 'Cinematic realistic shot, a smiling programmer hands small bags of gold coins to a line of excited people in a busy street, warm daylight, handheld camera',
 'Cinematic realistic shot, extreme close-up of a computer mouse cursor hovering over a glowing button on an old screen, a finger about to click the mouse, intense, slow push-in',
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
        print(which, int(k) + 1, round(time.time() - t1), 's', flush=True)
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
