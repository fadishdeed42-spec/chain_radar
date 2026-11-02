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

def refine_words(audio, sr, wt, thr_k=.06):
    """forced alignment can stretch a word over the silence before it ("ten" starting 0.5 s early): snap each word's
    start/end to where the voice really is (10 ms energy above 6 % of the loud level), never past the next word"""
    import numpy as np
    hop = int(.01 * sr)
    n = len(audio) // hop
    if n < 2: return wt
    e = np.sqrt((audio[:n * hop].reshape(n, hop).astype('float64') ** 2).mean(1))
    thr = thr_k * float(np.percentile(e, 95))
    out = []
    for k, (s, t) in enumerate(wt):
        a0, a1 = int(s * 100), max(int(s * 100) + 1, int(t * 100))
        seg = e[a0:a1]
        quiet = seg <= thr                                            # a pause swallowed by this word: start after it / end before it
        runs, k0 = [], None
        for j, q in enumerate(list(quiet) + [False]):
            if q and k0 is None: k0 = j
            if not q and k0 is not None:
                if j - k0 >= 12: runs.append((k0, j))
                k0 = None
        for r0, r1 in runs:
            if r0 < .7 * len(seg) and r1 < len(seg) - 4: s = (a0 + r1) / 100.0; a0b = a0 + r1; seg = e[a0b:a1]; a0 = a0b
            elif r0 > 2: t = (a0 + r0) / 100.0 + .02; seg = e[a0:a0 + r0]; break
        on = np.where(seg > thr)[0]
        if len(on) and t - s > .08:
            ns = (a0 + on[0]) / 100.0; ne = (a0 + on[-1] + 1) / 100.0 + .02
            if ne - ns >= .06: s, t = ns, min(t, ne)
        out.append((s, t))
    for k in range(1, len(out)):                                     # keep order: no word starts before the previous ends
        if out[k][0] < out[k - 1][1]: out[k] = (out[k - 1][1], max(out[k][1], out[k - 1][1]))
    return out


def ts(x): h, r = divmod(x, 3600); m, s = divmod(r, 60); return f'{int(h):02d}:{int(m):02d}:{s:06.3f}'.replace('.', ',')

def jhash(path):  # hash of the job, ignoring the (temporary) download link
    c = json.load(open(path)); c.pop('url', None)
    import hashlib; return hashlib.sha1(json.dumps(c, sort_keys=True).encode()).hexdigest()[:12]
