"""Emotional voice (Chatterbox, MIT) with the am_liam sound (Kokoro, Apache-2.0) as reference. Owner's pick Oct 12 2026.
Run by .github/workflows/cvoice.yml: python engine/cvoice.py engine/voice/v15c.json
json: {"engine": "chatterbox", "ref": "am_liam", "cfg": 0.2,
       "scenes": [["text", exaggeration, gap_after_s, "end"?], ...]}
  - one scene = one breath / one emotion; exaggeration 0.5 calm .. 0.9 big punchline
  - "end" on the story's last line: generated slower (cfg .35) and its natural tail is kept -> a finished, falling ending
  - spell names as they sound (Quadriga C X, Artoo Deetoo, Maker dow); captions are fixed in btNN.py
Output: <name>.wav (24k), <name>_words.srt (forced-aligned word times), <name>.srt (per scene), <name>.mp3, <name>.log"""
import sys, os, json
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align import align_words, refine_words, ts, jhash

def kok_ref(path):
    from kokoro import KPipeline
    pipe = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
    t = ("This CEO took the passwords to his grave. Allegedly. Gerald Cotton ran a Canadian crypto exchange. "
         "December twenty eighteen: he dies in India. Then: oops. Only Gerry had the keys.")
    a = np.concatenate([np.asarray(x, np.float32) for _, _, x in pipe(t, voice='am_liam', speed=1.05)])
    sf.write(path, a, 24000)

def trim(w, sr, tail):
    """cut silence around a take without touching soft word starts: find speech by short-window energy, keep 60 ms before it, smooth fades"""
    win = int(.01 * sr)
    if len(w) < win * 4: return w
    e = np.sqrt(np.convolve(w ** 2, np.ones(win) / win, mode='same'))
    nz = np.where(e > max(.0015, .015 * e.max()))[0]               # 1.5 %: soft word endings ("s", falling vowels) are kept, not chopped
    if not len(nz): return w
    on = np.where(e > max(.0008, .006 * e.max()))[0]                  # the start uses a lower bar: soft first sounds ("s", "f", "th") are kept whole
    st = on[0] if len(on) and on[0] < nz[0] else nz[0]
    w = w[max(0, st - int(.15 * sr)):min(len(w), nz[-1] + int(tail * sr))].copy()
    fi, fo = int(.015 * sr), int(.09 * sr)
    w[:fi] *= np.linspace(0, 1, fi) ** .5
    w[-fo:] *= (.5 + .5 * np.cos(np.linspace(0, np.pi, fo)))           # long cosine fade: lines end naturally, never a sharp stop
    return w


def level(w, target=.075):
    """every line at the same loudness (speech-only RMS), so no line or first word sounds quieter than the rest"""
    e = np.abs(w); thr = .1 * e.max()
    sp = w[e > thr]
    r = float(np.sqrt((sp ** 2).mean())) if len(sp) > 100 else float(np.sqrt((w ** 2).mean()))
    g = min(4.0, target / max(1e-5, r))
    w = w * g
    pk = np.abs(w).max()
    return w * (.95 / pk) if pk > .95 else w

_asr = None
LAST_RUSHED = []
def asr_wer(w, sr, text):
    """speech recognition check: share of script words the take got wrong (catches misread words)"""
    global _asr
    import difflib, re
    from faster_whisper import WhisperModel
    if _asr is None: _asr = WhisperModel('base.en', device='cpu', compute_type='int8')
    import librosa
    y = librosa.resample(w, orig_sr=sr, target_sr=16000)
    segs = list(_asr.transcribe(y, language='en', beam_size=1, word_timestamps=True)[0])
    got = ' '.join(s.text for s in segs)
    global LAST_RUSHED
    LAST_RUSHED = [w.word.strip() for s in segs for w in (s.words or [])                 # a long word squeezed into a blink = hard to understand
                   if len(re.sub(r'\W', '', w.word)) >= 6 and (w.end - w.start) < .032 * len(re.sub(r'\W', '', w.word)) + .04]
    def n(t):                                                     # both sides as spoken words: "$6.3 billion" == "six point three billion dollars"
        t = re.sub(r'(\d)\s*[-–]\s*(\d)', r'\1 to \2', t)           # "2014-2017" heard == "2014 to 2017" said
        try:
            import story
            t = ' '.join(w for _, sp in story.plan_line(t) for w in sp)
        except Exception:
            pass
        return [w[:-1] if w in ('dollars', 'percents') else w for w in re.sub(r"[^a-z ]", ' ', t.lower().replace('-', ' ')).split()]
    a, b = n(text), n(got)
    return 1 - difflib.SequenceMatcher(None, a, b).ratio(), got

def end_slope(w, sr, text):
    """pitch movement (semitones) over the last word: < 0 falls (finished), > 0 rises (sounds unfinished)"""
    import librosa
    words = text.split(); wt = align_words(w, sr, words); a0, a1 = wt[-1]
    seg = w[int(a0 * sr):int(a1 * sr) + int(.05 * sr)]
    if len(seg) < int(.12 * sr): return 0.0
    f0, vf, _ = librosa.pyin(seg, fmin=65, fmax=320, sr=sr, frame_length=1024)
    v = f0[~np.isnan(f0)]
    if len(v) < 6: return 0.0
    k = max(2, len(v) // 3)
    return float(12 * np.log2(np.median(v[-k:]) / np.median(v[:k])))

def phonetic_variant(said, heard):
    """The voice keeps misreading a word: ask Gemini how to spell it so a voice says it right ("Chainalysis" -> "Chain-alysis").
    Returns a new text with the same number of words, or None."""
    import re, difflib, requests
    keys = [k for k in (os.environ.get('GEMINI_API_KEY', ''), os.environ.get('GEMINI_API_KEY_2', '')) if k]
    a = said.split(); b = re.sub(r"[^\w' -]", ' ', heard).split()
    sm = difflib.SequenceMatcher(None, [re.sub(r'\W', '', x).lower() for x in a], [x.lower() for x in b])
    bad = sorted({a[k] for op, i1, i2, _, _ in sm.get_opcodes() if op in ('replace', 'delete') for k in range(i1, i2)
                  if len(re.sub(r'\W', '', a[k])) > 2 and a[k][:1].isupper() and k > 0 and not re.search(r'\d', a[k])})   # only NAMES get respelled, never years or normal words
    if not keys or not bad: return None
    prompt = ('A text-to-speech voice misreads these words in the sentence below. For each, give ONE respelling (letters and hyphens only, no spaces) that makes '
              f'an English voice say it correctly.\nSentence: {said}\nThe voice said: {heard}\nWords: {bad}\nReturn JSON only: {{"word": "respelling", ...}}')
    for key, model in [(k, m) for k in keys for m in ('gemini-flash-latest', 'gemini-flash-lite-latest', 'gemini-2.5-flash')]:
        try:
            r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', params={'key': key}, timeout=25,
                              json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'}})
            if not r.ok: print('phonetic', model, r.status_code); continue
            m = json.loads(re.search(r'\{.*\}', r.json()['candidates'][0]['content']['parts'][0]['text'], re.S).group(0))
            out = [(m.get(re.sub(r'[^\w-]', '', w)) or m.get(w) or w) if w in bad else w for w in a]          # touch only the misread names
            out = [re.sub(r'\s+', '-', str(x)) + (re.search(r'[.,!?;:]+$', w).group(0) if re.search(r'[.,!?;:]+$', w) and not re.search(r'[.,!?;:]$', str(x)) else '') for x, w in zip(out, a)]
            txt = ' '.join(out)
            return txt if txt != said and len(txt.split()) == len(a) else None
        except Exception as e:
            print('phonetic fail', repr(e)[:80])
    return None

def flow_report(audio, sr, wt, owner, base):
    """measure what a listener hears: pauses inside lines (hangs), gaps between lines, and line ends that stop sharply"""
    rep = {'hangs': [], 'sharp_ends': [], 'line_gaps': []}
    for k in range(len(wt) - 1):
        g = wt[k + 1][0] - wt[k][1]
        if owner[k] == owner[k + 1] and g > .7: rep['hangs'].append([round(wt[k][1], 2), round(g, 2)])
        if owner[k] != owner[k + 1]: rep['line_gaps'].append(round(g, 2))
    env = lambda a, b: float(np.sqrt((audio[max(0, int(a * sr)):max(int(a * sr) + 1, int(b * sr))] ** 2).mean()))
    for k in range(len(wt)):
        if k == len(wt) - 1 or owner[k] != owner[k + 1]:
            e1 = wt[k][1]; body = env(wt[k][0], e1); tail = env(e1 + .12, e1 + .16)
            if body > 0 and tail / body > .35: rep['sharp_ends'].append([round(e1, 2), round(tail / body, 2)])
    json.dump(rep, open(base + '_flow.json', 'w'), indent=1)
    return f"flow: {len(rep['hangs'])} hangs >0.7s inside lines, {len(rep['sharp_ends'])} possible sharp line ends, line gaps {rep['line_gaps']}"


def run(path):
    import torch
    from chatterbox.tts import ChatterboxTTS
    cfg = json.load(open(path)); base = path[:-5]; log = ['json ' + jhash(path)]
    ref = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"ref_{cfg.get('ref', 'am_liam')}.wav")   # made once, reused for every Short
    if not os.path.exists(ref): kok_ref(ref)
    torch.manual_seed(cfg.get('seed', 7))
    m = ChatterboxTTS.from_pretrained(device='cpu'); sr = m.sr
    parts, words, owner = [np.zeros(int(.12 * sr), np.float32)], [], []
    alts = cfg.get('alt') or []; checks = cfg.get('check') or []
    quality = []
    for i, sc in enumerate(cfg['scenes']):
        t, ex, gap = sc[0], sc[1], sc[2]; end = len(sc) > 3 and sc[3] == 'end'
        alt = alts[i] if i < len(alts) else None
        chk = checks[i] if i < len(checks) else t
        variants = [t] + ([alt] if alt else [])                     # respelled text and the plain text: whichever the voice says right wins
        n_max = 6 if end else 4                                     # fewer wasted takes: misread names go to the phonetic retry instead
        target = 2.35 if end else 2.6; best = None                     # calm, clear storytelling pace (fast takes swallowed words)
        for k in range(n_max):
            tt = variants[k % len(variants)]
            w = m.generate(tt, audio_prompt_path=ref, exaggeration=ex, cfg_weight=.35 if end else cfg.get('cfg', .2))
            w = trim(w.squeeze().numpy().astype(np.float32), sr, .5 if end else .22)
            try:
                wer, heard = asr_wer(w, sr, chk); rushed = list(LAST_RUSHED)
                if tt != chk: wer = min(wer, asr_wer(w, sr, tt)[0])
            except Exception as e: wer, heard, rushed = 0.0, f'asr failed {e}', []
            try: sl = end_slope(w, sr, tt)
            except Exception: sl = 0.0
            wps = len(tt.split()) / (len(w) / sr)
            want_up = tt.rstrip().endswith('?')
            ok_end = (sl > 0) if want_up else (sl < -1.0)
            score = 2.0 * ok_end - 6.0 * wer - .6 * abs(wps - target) - 1.5 * max(0, wps - 2.9) - .8 * len(rushed) - (.08 * max(0, sl) if not want_up else 0)
            log.append(f'   take {k+1}{" (plain)" if tt is alt else ""}: score {score:+.2f}  wer {wer:.2f}  end {sl:+.1f}st  {wps:.1f}w/s' + (f'  rushed {rushed}' if rushed else '') + f'  heard: {heard.strip()[:70]}')
            if best is None or (round(wer, 3), -score) < (round(best[2], 3), -best[0]): best = (score, w, wer, heard, tt)   # a wrong word ('finance' for 'Binance') loses to any take that says every word right
            good_words = wer <= .02 and not rushed
            if good_words and (ok_end or k >= 2) and k >= (1 if end else 0):   # every word right (and a finished ending when possible): stop early
                break
        def name_missed(said, heard):                               # a NAME the listener didn't hear right counts even when the rest is perfect
            import difflib, re as _re
            a = said.split(); b = [_re.sub(r'\W', '', x).lower() for x in heard.split()]
            sm = difflib.SequenceMatcher(None, [_re.sub(r'\W', '', x).lower() for x in a], b)
            return any(a[k][:1].isupper() and k > 0 and len(_re.sub(r'\W', '', a[k])) > 2
                       for op, i1, i2, _, _ in sm.get_opcodes() if op in ('replace', 'delete') for k in range(i1, i2))
        if best[2] > .08 or name_missed(chk, best[3]):              # misread word or name after every take: try a phonetic spelling of just those words
            ph = phonetic_variant(chk, best[3])
            if ph:
                log.append(f'   phonetic variant: {ph[:90]}')
                for k in range(3):
                    w = m.generate(ph, audio_prompt_path=ref, exaggeration=ex, cfg_weight=.35 if end else cfg.get('cfg', .2))
                    w = trim(w.squeeze().numpy().astype(np.float32), sr, .5 if end else .22)
                    try: wer, heard = asr_wer(w, sr, chk)
                    except Exception as e: wer, heard = 1.0, f'asr failed {e}'
                    wps = len(ph.split()) / (len(w) / sr)
                    score = -6.0 * wer - .6 * abs(wps - target) - 1.5 * max(0, wps - 3.05)
                    log.append(f'   take P{k+1}: score {score:+.2f}  wer {wer:.2f}  {wps:.1f}w/s  heard: {heard.strip()[:70]}')
                    if wer < best[2] - .02: best = (score, w, wer, heard, ph)
                    if wer <= .06: break
        if best[2] > .08:                                           # still a wrong/extra/repeated word: more plain takes until one is clean
            for k in range(4):
                w = m.generate(t, audio_prompt_path=ref, exaggeration=ex, cfg_weight=.35 if end else cfg.get('cfg', .2))
                w = trim(w.squeeze().numpy().astype(np.float32), sr, .5 if end else .22)
                try: wer, heard = asr_wer(w, sr, chk)
                except Exception as e: wer, heard = 1.0, f'asr failed {e}'
                log.append(f'   take R{k+1}: wer {wer:.2f}  heard: {heard.strip()[:70]}')
                if wer < best[2] - .02: best = (0.0, w, wer, heard, t)
                if wer <= .06: break
        _, w, wer, heard, tt = best
        w = level(w)
        parts += [w, np.zeros(int(gap * sr), np.float32)]
        for x in tt.split(): words.append(x); owner.append(i)
        quality.append({'scene': i + 1, 'wer': round(wer, 3), 'heard': heard.strip()[:160], 'said': chk[:160]})
        log.append(f'scene {i+1}: {len(w)/sr:.2f}s ex {ex}{" END" if end else ""}  chosen wer {wer:.2f}')
    json.dump(quality, open(base + '_quality.json', 'w'), indent=1)
    audio = np.concatenate(parts); audio = audio / max(1e-6, np.abs(audio).max()) * .9
    try:                                                          # even loudness: no quiet first word ("gone"), no soft line endings
        import subprocess, tempfile
        a_, b_ = tempfile.mktemp(suffix='.wav'), tempfile.mktemp(suffix='.wav'); sf.write(a_, audio, sr)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', a_, '-af',
                        'acompressor=threshold=-21dB:ratio=2.2:attack=12:release=220:knee=6,highpass=f=70,alimiter=limit=0.95:attack=5:release=60',
                        b_], check=True)
        lev, _ = sf.read(b_, dtype='float32')
        if len(lev) >= len(audio) - sr // 10: audio = lev[:len(audio)] if len(lev) >= len(audio) else np.pad(lev, (0, len(audio) - len(lev)))
        os.remove(a_); os.remove(b_); log.append('lines levelled + gentle compressor (no pumping)')
    except Exception as e:
        log.append(f'leveling skipped {e}')
    wt = refine_words(audio, sr, align_words(audio, sr, words)); log.append(f'{len(audio)/sr:.2f}s, force-aligned {len(words)} words (snapped to the voice)')
    cues = []
    for i, sc in enumerate(cfg['scenes']):
        idx = [k for k in range(len(words)) if owner[k] == i]; cues.append((wt[idx[0]][0], wt[idx[-1]][1], sc[0]))
    sf.write(base + '.wav', audio, sr)
    open(base + '.srt', 'w').write('\n'.join(f'{i+1}\n{ts(a)} --> {ts(b)}\n{t}\n' for i, (a, b, t) in enumerate(cues)))
    open(base + '_words.srt', 'w').write('\n'.join(f'{i+1}\n{ts(a)} --> {ts(b)}\n{t}\n' for i, ((a, b), t) in enumerate(zip(wt, words))))
    os.system(f'ffmpeg -y -loglevel error -i {base}.wav -b:a 160k {base}.mp3')
    lv = cfg.get('liam')                          # re-time to the original Liam take (pace + pauses); no take -> Liam-rate pacing
    d = os.path.dirname(path); import subprocess
    has = bool(lv) and os.path.exists(os.path.join(d, str(lv) + '.wav'))
    if os.environ.get('LIAMPACE') == '1':
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'liampace.py'), base + '.wav', base + '_words.srt',
                            f'{d}/{lv}.wav' if has else '-', f'{d}/{lv}_words.srt' if has else '-', base + 'p'], capture_output=True, text=True)
        log.append('liampace -> ' + base + 'p.wav\n' + r.stdout + r.stderr)
    else:                                                          # Nov 2: re-cutting sentences on aligned word times chopped word endings and
        import shutil                                              # put dead 0.4 s holes inside lines -> keep each take whole, gaps set per line
        shutil.copy(base + '.wav', base + 'p.wav'); shutil.copy(base + '_words.srt', base + 'p_words.srt')
        os.system(f'ffmpeg -y -loglevel error -i {base}p.wav -b:a 160k {base}p.mp3')
        log.append('takes kept whole (no sentence re-cut) -> ' + base + 'p.wav')
    try:
        log.append(flow_report(audio, sr, wt, owner, base))
    except Exception as e:
        log.append(f'flow report failed {e}')
    open(base + '.log', 'w').write('\n'.join(log) + '\n'); print('\n'.join(log))

if __name__ == '__main__':
    for p in sys.argv[1:]: run(p)
