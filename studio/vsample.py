"""Voice samples: the same opening read in a few styles, each sent to Telegram as audio so the owner can pick by ear.
python studio/vsample.py  (variants below; refs are Kokoro voices used as the Chatterbox reference)"""
import os, sys, numpy as np, soundfile as sf, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cvoice
from run import tg
LINES = ["In twenty thirteen, Bitcoin split into two chains.",
         "And developers chose to kill the newer one.",
         "March eleventh, twenty thirteen. Bitcoin version zero point eight was brand new.",
         "Then one huge block hit the network, with over five thousand transactions."]
#            name, label, kokoro ref, exaggeration per line, cfg, gap
VARIANTS = [("A", "Liam, calm - punchy only on key words", "am_liam", [.7, .6, .4, .5], .4, .45),
            ("B", "Deep documentary voice", "am_onyx", [.6, .55, .4, .45], .45, .5),
            ("C", "Slow mystery / true-crime voice", "bm_george", [.5, .5, .35, .45], .5, .6)]
from chatterbox.tts import ChatterboxTTS
m = ChatterboxTTS.from_pretrained(device='cpu')
here = os.path.dirname(os.path.abspath(__file__))
for name, label, ref, ex, cfg, gap in VARIANTS:
    rp = os.path.join(here, f'ref_{ref}.wav')
    if not os.path.exists(rp): cvoice.kok_ref(rp, ref)
    parts = []
    for line, e in zip(LINES, ex):
        best = None
        for seed in (7, 8):
            import torch; torch.manual_seed(seed)
            w = m.generate(line, audio_prompt_path=rp, exaggeration=e, cfg_weight=cfg).squeeze().numpy()
            w = cvoice.level(cvoice.trim(w, m.sr, .25))
            wer, heard = cvoice.asr_wer(w, m.sr, line)
            print(name, seed, round(wer, 2), heard)
            if best is None or wer < best[0]: best = (wer, w)
        parts += [best[1], np.zeros(int(gap * m.sr), np.float32)]
    a = np.concatenate(parts)
    sf.write(f'/tmp/v{name}.wav', a, m.sr)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', f'/tmp/v{name}.wav', '-b:a', '160k', f'/tmp/voice_{name}.mp3'], check=True)
    tg('sendAudio', {'caption': f'🎙 Voice <b>{name}</b>: {label}'}, files={'audio': open(f'/tmp/voice_{name}.mp3', 'rb')})
tg('sendMessage', {'text': 'Which voice fits best? Reply in Claude: A, B or C.'})
