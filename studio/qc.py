"""Chain Secrets quality checker — script, voice and finished video.

Every check reports one of: ok / warn / fail / skip. A check that could not run is 'skip' and is shown as
"not checked" — it is never reported as passed. The owner is the last check: the bot shows this report at
each checkpoint (script -> voice -> video) and waits for approval.

    import qc
    items = qc.script(sb, facts)          # in the bot, before the voice is made
    items = qc.voice(job_dir)             # on GitHub, after the voice
    items = qc.video(path, T, job_dir)    # on GitHub, after the render
    qc.report(items, 'Voice')             # short Telegram text
"""
import os, re, json, subprocess

OK, WARN, FAIL, SKIP = 'ok', 'warn', 'fail', 'skip'
ICON = {OK: '✅', WARN: '⚠️', FAIL: '❌', SKIP: '➖'}
def it(level, area, msg): return {'level': level, 'area': area, 'msg': msg}

# ---------------------------------------------------------------- helpers
_NUMW = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
def numbers_in(text):
    """every number written in a line, normalised: '$6.3 billion' -> 6.3, '61,000' -> 61000, '2014' -> 2014"""
    out = set()
    for m in re.finditer(r'\$?\d[\d,]*(?:\.\d+)?', text):
        s = m.group(0).replace('$', '').replace(',', '')
        try: out.add(float(s))
        except ValueError: pass
    return out
def _ok_number(n, facts_nums, facts_text):
    if n in facts_nums: return True
    if n < 10 and n == int(n): return True                                   # "two pizzas", "3 days": too small to be a claim
    if 1990 <= n <= 2035 and str(int(n)) in facts_text: return True
    for f in facts_nums:                                                      # 6.3 vs 6,300,000,000 / rounding to 2 significant digits
        if f and (abs(f - n) / max(f, n) < .02 or any(abs(f / k - n) / max(n, 1e-9) < .02 for k in (1e3, 1e6, 1e9, 1e12))): return True
    return False
START_WEAK = re.compile(r"^(this is|today|in (19|20)\d\d|meet|let me|have you|did you know|imagine|once upon|so,|here's the story|the story of)", re.I)

# ---------------------------------------------------------------- 1. script (runs in the bot before any voice is made)
def script(sb, facts=''):
    r = []
    sc = sb.get('scenes') or []
    lines = [str(s.get('line', '')).strip() for s in sc]
    if not lines: return [it(FAIL, 'script', 'no lines')]
    first = lines[0]
    # hook: the first line must carry the shock (a number, a name or a strong word), not a setup
    if START_WEAK.search(first): r.append(it(FAIL, 'hook', f'line 1 starts like a setup ("{first[:40]}…"). Start with the shock.'))
    elif not (numbers_in(first) or re.search(r'\b[A-Z][a-z]{2,}', first[1:]) or len(first.split()) <= 7):
        r.append(it(WARN, 'hook', 'line 1 has no number or name — is it a shock in the first second?'))
    else: r.append(it(OK, 'hook', 'line 1 is a hook'))
    if len(first.split()) > 14: r.append(it(WARN, 'hook', f'line 1 is {len(first.split())} words — the hook should land within ~2 s (≤ 12 words)'))
    # sentence length
    long_ = [(i + 1, len(x.split())) for i, l in enumerate(lines) for x in re.split(r'(?<=[.!?])\s+', l) if len(x.split()) > 22]
    r.append(it(WARN, 'pacing', 'long sentences: ' + ', '.join(f'line {a} ({b} words)' for a, b in long_)) if long_ else it(OK, 'pacing', 'no sentence over 22 words'))
    # repeated wording
    seen, rep = {}, []
    for i, l in enumerate(lines):
        for w in set(re.findall(r'[a-z]{5,}', l.lower())) - {'bitcoin', 'crypto', 'million', 'billion', 'there', 'their', 'about', 'which', 'would'}:
            if w in seen and i - seen[w] <= 1: rep.append(w)
            seen[w] = i
    if len(rep) >= 2: r.append(it(WARN, 'wording', 'same word in back-to-back lines: ' + ', '.join(sorted(set(rep))[:5])))
    # facts: every number in the script must be in the research
    ftxt = (facts or '') + ' ' + str(sb.get('facts_text', ''))
    if ftxt.strip():
        fn = numbers_in(ftxt.replace(',', ''))
        fn |= numbers_in(ftxt)
        miss = [(i + 1, n) for i, l in enumerate(lines) for n in numbers_in(l) if not _ok_number(n, fn, ftxt)]
        r.append(it(FAIL, 'facts', 'numbers not in the research: ' + ', '.join(f'line {a}: {b:g}' for a, b in miss[:6])) if miss
                 else it(OK, 'facts', 'every number is in the research'))
    else:
        r.append(it(SKIP, 'facts', 'no research saved for this script, numbers not checked'))
    rv = sb.get('review') or {}
    if rv: r.append(it(FAIL, 'facts', 'fact-check could not confirm lines ' + ', '.join(sorted(rv, key=int))))
    # loop ending: the last story line should point back to the start
    story_lines = [l for s, l in zip(sc, lines) if s.get('role') != 'cta'] or lines
    a = set(re.findall(r'[a-z0-9]{4,}', first.lower())); b = set(re.findall(r'[a-z0-9]{4,}', story_lines[-1].lower()))
    r.append(it(OK, 'loop', 'ending echoes the opening') if a & b else it(WARN, 'loop', 'ending does not loop back to the first line'))
    # length
    est = sb.get('est_secs')
    if est: r.append(it(OK if sb.get('length_ok', True) else WARN, 'length', f'~{est:.0f}s estimated'))
    return r

# ---------------------------------------------------------------- 2. voice (runs on GitHub after the voice)
def _srt(p):
    out = []
    for blk in open(p).read().strip().split('\n\n'):
        l = blk.strip().split('\n')
        if len(l) < 3: continue
        a, b = l[1].split(' --> ')
        f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + float(x[6:].replace(',', '.'))
        out.append((f(a), f(b), ' '.join(l[2:])))
    return out
def voice(d):
    r = []
    try: q = json.load(open(f'{d}/voice_quality.json'))
    except Exception: q = None
    if not q: r.append(it(SKIP, 'words', 'speech check missing'))
    else:
        bad = [x for x in q if x.get('wer', 0) > .1]
        r.append(it(FAIL, 'words', 'misheard: ' + '; '.join(f'line {x["scene"]} heard "{x["heard"][:60]}"' for x in bad[:3])) if bad
                 else it(OK, 'words', f'all {len(q)} lines heard correctly'))
        # names / hard words: every capitalised word of the script must be heard (the WER can pass while a name is wrong)
        names = []
        for x in q:
            heard = x.get('heard', '').lower()
            for w in re.findall(r"\b[A-Z][a-zA-Z']{3,}\b", x.get('said', '')):
                if w.lower() not in heard and w.lower() not in ('follow', 'every', 'chain', 'secrets', 'subscribe', 'more', 'stories', 'then', 'they', 'this', 'that', 'when', 'what', 'here'):
                    names.append((x['scene'], w))
        r.append(it(WARN, 'names', 'listen to: ' + ', '.join(f'line {a} "{b}"' for a, b in names[:5])) if names else it(OK, 'names', 'every name was heard'))
    try: fl = json.load(open(f'{d}/voice_flow.json'))
    except Exception: fl = None
    if fl is None: r.append(it(SKIP, 'flow', 'pause check missing'))
    else:
        h = [x for x in fl.get('hangs', []) if x[1] > .6]
        r.append(it(WARN, 'flow', 'pauses inside a sentence at ' + ', '.join(f'{a:.1f}s ({b:.1f}s)' for a, b in h[:4])) if h else it(OK, 'flow', 'no hangs inside sentences'))
        s = fl.get('sharp_ends', [])
        r.append(it(WARN, 'endings', f'{len(s)} line endings may stop sharply (at ' + ', '.join(f'{a:.1f}s' for a, _ in s[:3]) + ')') if s else it(OK, 'endings', 'line endings fade naturally'))
    if os.path.exists(f'{d}/voicep_words.srt'):
        w = _srt(f'{d}/voicep_words.srt')
        if len(w) > 5:
            speak = sum(b - a for a, b, _ in w); gaps = [w[i + 1][0] - w[i][1] for i in range(len(w) - 1)]
            wps = len(w) / max(1e-6, (w[-1][1] - w[0][0]) - sum(g for g in gaps if g > .45))
            lvl = OK if 2.2 <= wps <= 3.4 else WARN
            r.append(it(lvl, 'pace', f'{wps:.1f} words/s' + ('' if lvl == OK else (' — too fast' if wps > 3.4 else ' — too slow'))))
            if w[0][0] > .8: r.append(it(WARN, 'start', f'voice starts at {w[0][0]:.1f}s — the hook should start at once'))
    try:
        import numpy as np, soundfile as sf
        a, sr = sf.read(f'{d}/voicep.wav', dtype='float32')
        a = a.mean(1) if a.ndim > 1 else a
        clip = int((np.abs(a) > .985).sum())
        r.append(it(WARN, 'audio', f'{clip} clipped samples') if clip > 50 else it(OK, 'audio', 'no clipping'))
    except Exception as e:
        r.append(it(SKIP, 'audio', 'clipping not checked'))
    return r

# ---------------------------------------------------------------- 3. finished video (runs on GitHub after the render)
def _probe(path):
    x = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height,avg_frame_rate,duration', '-of', 'json', path], capture_output=True, text=True).stdout
    return json.loads(x or '{}').get('streams', [])
def _frames(path, times, w=360):
    import numpy as np
    out = []
    for t in times:
        p = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t):.2f}', '-i', path, '-frames:v', '1', '-vf', f'scale={w}:-2', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'], capture_output=True)
        out.append(p.stdout)
    return out
def video(path, T, d=None, sb=None):
    r = []
    st = _probe(path)
    v = next((s for s in st if s.get('codec_type') == 'video'), {}); a = next((s for s in st if s.get('codec_type') == 'audio'), {})
    if (v.get('width'), v.get('height')) != (1080, 1920): r.append(it(FAIL, 'format', f'size {v.get("width")}x{v.get("height")}, needs 1080x1920'))
    else: r.append(it(OK, 'format', '1080x1920 vertical'))
    vd, ad = float(v.get('duration') or 0), float(a.get('duration') or 0)
    if not a: r.append(it(FAIL, 'audio', 'no sound track'))
    elif abs(vd - ad) > .4: r.append(it(FAIL, 'sync', f'picture {vd:.1f}s vs sound {ad:.1f}s'))
    else: r.append(it(OK, 'sync', f'picture and sound both {vd:.1f}s'))
    if vd > 61: r.append(it(WARN, 'length', f'{vd:.0f}s — over a minute; your best Shorts are 35–45 s'))
    # loudness
    lg = subprocess.run(['ffmpeg', '-v', 'info', '-i', path, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = re.findall(r'I:\s+(-?[\d.]+) LUFS', lg); P = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', lg)
    if I:
        i_ = float(I[-1]); pk = float(P[-1]) if P else -99
        r.append(it(OK if -15.5 <= i_ <= -12.5 else WARN, 'loudness', f'{i_:.1f} LUFS (target −14)'))
        if pk > -.5: r.append(it(WARN, 'loudness', f'peak {pk:.1f} dB — may distort'))
    else: r.append(it(SKIP, 'loudness', 'not measured'))
    # black frames and frozen picture (outside the end card)
    end_card = (T.get('cta') or T.get('dur', vd)) - .5
    lg = subprocess.run(['ffmpeg', '-v', 'info', '-i', path, '-vf', 'blackdetect=d=0.3:pix_th=0.06,freezedetect=n=0.003:d=1.3', '-map', '0:v', '-f', 'null', '-'], capture_output=True, text=True).stderr
    blk = [float(x) for x in re.findall(r'black_start:([\d.]+)', lg) if float(x) < end_card]
    frz = [float(x) for x in re.findall(r'freeze_start: ([\d.]+)', lg) if float(x) < end_card]
    r.append(it(FAIL, 'picture', 'black frames at ' + ', '.join(f'{x:.1f}s' for x in blk[:3])) if blk else it(OK, 'picture', 'no black frames'))
    r.append(it(WARN, 'picture', 'frozen picture at ' + ', '.join(f'{x:.1f}s' for x in frz[:3])) if frz else it(OK, 'motion', 'picture keeps moving'))
    # visual review by Gemini (free tier): first frame hook, cut-off/overlapping text, picture matches the words
    r += vision(path, T, d, sb, vd)
    return r

def _line_at(T, d, t):
    """the words spoken in the 3 s before a moment of the finished video (timing.json is in video time)"""
    try:
        return ' '.join(w[3] for w in T.get('words', []) if t - 3 <= w[2] <= t + .4)[-160:]
    except Exception: return ''
def vision(path, T, d, sb, dur):
    import base64, requests, time
    keys = [k for k in (os.environ.get('GEMINI_API_KEY', ''), os.environ.get('GEMINI_API_KEY_2', '')) if k]
    if not keys: return [it(SKIP, 'visual', 'Gemini key missing — visuals not reviewed')]
    times = [0.1] + [dur * f for f in (.15, .3, .45, .6, .75, .88)]
    jpgs = _frames(path, times)
    parts = [{'text': (
        'You are a strict video editor reviewing a vertical YouTube Short. For each numbered frame you get the narration spoken around it. '
        'Judge ONLY what you can see. Reply JSON: {"frames":[{"n":1,"cut_off_text":bool,"overlap":bool,"unreadable":bool,"matches_words":bool,"note":"max 10 words"}],'
        '"first_frame_hook":bool,"first_frame_note":"max 10 words"}. '
        'cut_off_text = any text touching or running past the frame edge. overlap = text/graphics covering other text. '
        'unreadable = text too small or low contrast for a phone. matches_words = the picture shows what the narration says (charts/titles about the same subject count). '
        'first_frame_hook = frame 1 already shows a big readable number or shocking statement (not an empty or title-only intro).')}]
    for n, (t, j) in enumerate(zip(times, jpgs), 1):
        if not j: continue
        parts.append({'text': f'Frame {n} at {t:.1f}s. Narration: "{_line_at(T, d, t)}"'})
        parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(j).decode()}})
    body = {'contents': [{'parts': parts}], 'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'}}
    js = None
    for rnd in range(3):
        if rnd: time.sleep(5 * rnd)
        for key in keys:
            for model in ('gemini-flash-latest', 'gemini-2.5-flash', 'gemini-flash-lite-latest'):
                try:
                    x = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', params={'key': key}, json=body, timeout=60)
                    if x.ok:
                        txt = ''.join(p.get('text', '') for p in x.json()['candidates'][0]['content']['parts'])
                        js = json.loads(re.search(r'\{.*\}', txt, re.S).group(0)); break
                except Exception as e:
                    print('qc vision', model, repr(e)[:80])
            if js: break
        if js: break
    if not js: return [it(SKIP, 'visual', 'Gemini did not answer — visuals not reviewed')]
    r = [it(OK if js.get('first_frame_hook') else FAIL, 'hook frame', 'first frame shows the hook' if js.get('first_frame_hook') else 'first frame is not a hook: ' + str(js.get('first_frame_note', ''))[:60])]
    fr = js.get('frames') or []
    for key, area, msg in (('cut_off_text', 'text', 'text cut off'), ('overlap', 'text', 'text overlapping'), ('unreadable', 'text', 'hard to read'), ('matches_words', 'match', 'picture may not match the words')):
        bad = [f for f in fr if (not f.get(key)) == (key == 'matches_words')]
        if bad:
            r.append(it(WARN, area, msg + ' at ' + ', '.join(f'{times[min(len(times), int(f.get("n", 1))) - 1]:.0f}s ({str(f.get("note", ""))[:30]})' for f in bad[:3])))
    if len(r) == 1: r.append(it(OK, 'visual', f'{len(fr)} frames reviewed: text readable, nothing cut off, pictures match'))
    return r

# ---------------------------------------------------------------- report
def verdict(items):
    lv = [x['level'] for x in items]
    return FAIL if FAIL in lv else WARN if WARN in lv else OK
def report(items, stage):
    v = verdict(items)
    head = {OK: f'✅ <b>{stage} check: passed</b>', WARN: f'⚠️ <b>{stage} check: please look at</b>', FAIL: f'❌ <b>{stage} check: problems found</b>'}[v]
    if v == OK and any(x['level'] == SKIP for x in items):
        head = f'✅ <b>{stage} check: passed</b> (some checks could not run, see ➖)'
    shown = [x for x in items if x['level'] in (FAIL, WARN)] + [x for x in items if x['level'] == SKIP]
    oks = [x for x in items if x['level'] == OK]
    import html
    lines = [f'{ICON[x["level"]]} {html.escape(x["area"])}: {html.escape(x["msg"])}' for x in shown[:8]]
    if oks: lines.append(f'✅ {len(oks)} checks passed (' + ', '.join(sorted({x["area"] for x in oks}))[:120] + ')')
    return head + '\n' + '\n'.join(lines)
def save(d, stage, items):
    p = f'{d}/qc.json'
    try: allq = json.load(open(p))
    except Exception: allq = {}
    allq[stage] = {'verdict': verdict(items), 'items': items}
    json.dump(allq, open(p, 'w'), indent=1)
