# Runs INSIDE a Kaggle GPU notebook: one short text-to-video clip with an open model (LTX-Video), saved to /kaggle/working/.
import os, subprocess, sys, time, json
t0 = time.time()
def run(c): print('$', c, flush=True); subprocess.run(c, shell=True, check=False)
run('nvidia-smi --query-gpu=name,memory.total --format=csv')
run(f'{sys.executable} -m pip install -q -U diffusers transformers accelerate sentencepiece imageio imageio-ffmpeg')
import torch
from diffusers import LTXPipeline
from diffusers.utils import export_to_video
print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), flush=True)
pipe = LTXPipeline.from_pretrained('Lightricks/LTX-Video', torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16)
pipe.enable_model_cpu_offload()
try: pipe.vae.enable_tiling()
except Exception as e: print('tiling', e)
prompt = ('A cartoon man in a white shirt sits at a poker table at night, slides a big pile of poker chips to the center, '
          'cinematic lighting, smoke, smooth camera push-in, 2D cartoon style')
neg = 'worst quality, blurry, jittery, distorted, watermark'
t1 = time.time()
out = pipe(prompt=prompt, negative_prompt=neg, width=480, height=704, num_frames=65, num_inference_steps=30, generator=torch.Generator('cpu').manual_seed(7)).frames[0]
secs = time.time() - t1
export_to_video(out, '/kaggle/working/test.mp4', fps=24)
json.dump({'gen_seconds': round(secs, 1), 'total_seconds': round(time.time() - t0, 1), 'frames': len(out)}, open('/kaggle/working/timing.json', 'w'))
print('DONE gen_seconds', round(secs, 1), flush=True)
