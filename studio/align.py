"""Forced word alignment (torchaudio MMS_FA) + SRT helpers, from the Chain Secrets engine."""
import re, json

def align_words(audio, sr, words):
    """Exact forced alignment of the known script words (torchaudio MMS_FA). Returns [(start,end)] per word."""
    import torch, torchaudio
    bundle = torchaudio.pipelines.MMS_FA
    model, tok, aligner = bundle.get_model(), bundle.get_tokenizer(), bundle.get_aligner()
    wav = torchaudio.functional.resample(torch.tensor(audio)[None], sr, bundle.sample_rate)
    keys = [re.sub(r"[^a-z']", '', w.lower()) for w in words]
    use = [i for i, k in enumerate(keys) if k]
    with torch.inference_mode():
        em, _ = model(wav)
        spans = aligner(em[0], tok([keys[i] for i in use]))
    ratio = wav.shape[1] / em.shape[1] / bundle.sample_rate
    out = [None] * len(words)
    for i, sp in zip(use, spans): out[i] = (sp[0].start * ratio, sp[-1].end * ratio)
    for i in range(len(out)):  # tokens with no letters: glue to previous word
        if out[i] is None: p = out[i - 1] if i else (0.0, 0.0); out[i] = (p[1], p[1])
    return out

def ts(x): h, r = divmod(x, 3600); m, s = divmod(r, 60); return f'{int(h):02d}:{int(m):02d}:{s:06.3f}'.replace('.', ',')

def jhash(path):  # hash of the job, ignoring the (temporary) download link
    c = json.load(open(path)); c.pop('url', None)
    import hashlib; return hashlib.sha1(json.dumps(c, sort_keys=True).encode()).hexdigest()[:12]
