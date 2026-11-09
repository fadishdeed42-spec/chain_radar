"""Real footage + photos for Studio Shorts (free sources only).

python media.py JOBDIR   -> JOBDIR/media/<scene>.mp4|.jpg + JOBDIR/media.json {scene: {kind, file, credit}}

Pixabay videos/photos (env PIXABAY_API_KEY, free, no attribution required, credited anyway)
Wikipedia/Wikimedia Commons lead photos for real people/companies (free licences only, attribution kept for the description).
Which scenes get media depends on the Studio "style": graphics/3d -> none, mixed -> people/places/actions, documentary -> every scene but charts."""
import os, sys, json, re, requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import story

UA = {'User-Agent': 'ChainSecretsStudio/1.0 (https://github.com/fadishdeed42-spec/chain_radar)'}
KEY = os.environ.get('PIXABAY_API_KEY', '')
MAXB = 40 * 1024 * 1024


def get(url, out):
    with requests.get(url, headers=UA, timeout=60, stream=True) as r:
        r.raise_for_status()
        n = 0
        with open(out, 'wb') as f:
            for c in r.iter_content(1 << 16):
                n += len(c)
                if n > MAXB: raise ValueError('too big')
                f.write(c)
    return out


def pixabay_video(q, used):
    if not KEY or not q: return None
    r = requests.get('https://pixabay.com/api/videos/', params={'key': KEY, 'q': q[:90], 'per_page': 20, 'safesearch': 'true'}, timeout=30)
    if not r.ok: print('pixabay video', r.status_code, r.text[:80]); return None
    best = None
    for h in r.json().get('hits', []):
        if h['id'] in used or h.get('duration', 0) < 4: continue
        vs = [h['videos'][k] for k in ('medium', 'small', 'tiny') if (h['videos'].get(k) or {}).get('url')]
        vs = [x for x in vs if not x.get('size') or x['size'] < MAXB] or vs[-1:]
        if not vs: continue
        v = vs[0]
        score = (2 if v.get('height', 0) > v.get('width', 1) else 0) + min(h.get('likes', 0), 300) / 300
        if best is None or score > best[0]: best = (score, h, v)
    if not best: return None
    _, h, v = best
    return {'kind': 'video', 'url': v['url'], 'small': (h['videos'].get('small') or {}).get('url'), 'id': h['id'], 'credit': f"Video: {h.get('user', 'Pixabay')} / Pixabay"}


def pixabay_videos(q, used, n=4):
    """up to n candidate videos for q, best first (vertical + liked ranks higher)"""
    if not KEY or not q: return []
    r = requests.get('https://pixabay.com/api/videos/', params={'key': KEY, 'q': q[:90], 'per_page': 20, 'safesearch': 'true'}, timeout=30)
    if not r.ok: print('pixabay video', r.status_code, r.text[:80]); return []
    c = []
    for h in r.json().get('hits', []):
        if h['id'] in used or h.get('duration', 0) < 4: continue
        vs = [h['videos'][k] for k in ('small', 'tiny', 'medium') if (h['videos'].get(k) or {}).get('url')]
        vs = [x for x in vs if not x.get('size') or x['size'] < MAXB]
        if not vs: continue
        v = vs[0]
        c.append(((2 if v.get('height', 0) > v.get('width', 1) else 0) + min(h.get('likes', 0), 300) / 300, {
            'kind': 'video', 'url': v['url'], 'id': h['id'], 'credit': f"Video: {h.get('user', 'Pixabay')} / Pixabay"}))
    return [m for _, m in sorted(c, key=lambda x: -x[0])[:n]]


def _clip_ok(path, min_s=2.5):
    """a usable clip: decodes, lasts min_s seconds, and actually moves (not a still picture saved as video)"""
    import cv2
    cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    if not 1 < fps < 121: fps = 30
    n, prev, diffs = 0, None, []
    while n < int(fps * 6):
        ok, fr = cap.read()
        if not ok: break
        if n % int(fps // 2 or 1) == 0:
            g = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (96, 160)).astype('float32')
            if prev is not None: diffs.append(float(abs(g - prev).mean()))
            prev = g
        n += 1
    cap.release()
    moving = sorted(diffs)[len(diffs) // 2] if diffs else 0.0
    ok = n >= fps * min_s and moving >= 1.2
    if not ok: print(f'  clip rejected: {n / fps:.1f}s, motion {moving:.1f}', os.path.basename(path))
    return ok


def _vision_ok(path, kind, words, q):
    """Does the picture literally show what the narration says? Gemini looks at one frame. Fails open (True) if it can't judge."""
    keys = [k for k in (os.environ.get('GEMINI_API_KEY', ''), os.environ.get('GEMINI_API_KEY_2', '')) if k]
    if not keys: return None
    import base64, cv2
    try:
        if kind == 'video':
            cap = cv2.VideoCapture(path); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n // 3)); ok, fr = cap.read(); cap.release()
        else:
            fr = cv2.imread(path); ok = fr is not None
        if not ok: return None
        h, w = fr.shape[:2]; k = 512 / max(h, w)
        fr = cv2.resize(fr, (int(w * k), int(h * k))) if k < 1 else fr
        b64 = base64.b64encode(cv2.imencode('.jpg', fr, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()).decode()
    except Exception as e:
        print('vision frame fail', repr(e)[:80]); return None
    prompt = (f'A short documentary video says: "{words}". We want a background picture that shows this literally (search was "{q}"). '
              'Does this frame fit? It must show the thing said (or a clearly related scene), not a random or misleading place/object '
              '(for example a temple for "government building", a door for "launched a company", animals, beaches, forests or confetti for news about hackers, money or courts, or a cartoon for a real event are NOT ok). '
              'Landscapes and nature only fit when the words are about that place or nature. When in doubt, answer false. '
              'Reply JSON only: {"ok": true or false, "why": "max 8 words"}')
    body = {'contents': [{'parts': [{'text': prompt}, {'inline_data': {'mime_type': 'image/jpeg', 'data': b64}}]}], 'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'}}
    import time as _t
    for rnd in range(4):                                            # Google busy: wait and ask again before letting a clip through unchecked
      if rnd: _t.sleep(4 * rnd)
      for key in keys:
        for model in ('gemini-flash-latest', 'gemini-flash-lite-latest'):
              try:
                  r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', params={'key': key}, json=body, timeout=30)
                  if r.ok:
                      t = ''.join(p.get('text', '') for p in r.json()['candidates'][0]['content']['parts'])
                      j = json.loads(re.search(r'\{.*\}', t, re.S).group(0))
                      print('  vision', 'OK ' if j.get('ok') else 'NO ', q, '|', j.get('why', ''))
                      return bool(j.get('ok'))
                  if r.status_code != 429: print('  vision', model, r.status_code); continue
              except Exception as e:
                  print('  vision err', repr(e)[:80])
    print('  vision: no answer -> clip not used'); return None   # never let an unchecked clip through

def pixabay_photo(q, used):
    if not KEY or not q: return None
    r = requests.get('https://pixabay.com/api/', params={'key': KEY, 'q': q[:90], 'per_page': 20, 'image_type': 'photo', 'safesearch': 'true'}, timeout=30)
    if not r.ok: return None
    for h in r.json().get('hits', []):
        if h['id'] in used: continue
        return {'kind': 'photo', 'url': h['largeImageURL'], 'id': h['id'], 'credit': f"Photo: {h.get('user', 'Pixabay')} / Pixabay"}


def wiki_photo(q):
    """lead photo of the best Wikipedia article for q, only if it lives on Commons under a free licence"""
    if not q: return None
    api = 'https://en.wikipedia.org/w/api.php'
    r = requests.get(api, headers=UA, timeout=30, params={'action': 'query', 'format': 'json', 'generator': 'search', 'gsrsearch': q, 'gsrlimit': 1,
                                                       'prop': 'pageimages', 'piprop': 'thumbnail|name', 'pithumbsize': 1200})
    pages = list((r.json().get('query') or {}).get('pages', {}).values())
    if not pages or not pages[0].get('thumbnail'): return None
    pg = pages[0]; name = pg.get('pageimage', '')
    r = requests.get(api, headers=UA, timeout=30, params={'action': 'query', 'format': 'json', 'titles': 'File:' + name, 'prop': 'imageinfo', 'iiprop': 'extmetadata'})
    info = list(r.json()['query']['pages'].values())[0]
    if info.get('imagerepository') != 'shared': return None                # not on Commons = probably fair use -> skip
    md = (info.get('imageinfo') or [{}])[0].get('extmetadata', {})
    lic = md.get('LicenseShortName', {}).get('value', '')
    if not lic or 'fair' in lic.lower() or 'non-free' in lic.lower(): return None
    artist = re.sub('<[^>]+>', '', md.get('Artist', {}).get('value', '')).strip()[:60] or 'Wikimedia Commons'
    return {'kind': 'photo', 'url': pg['thumbnail']['source'], 'id': name, 'credit': f'Photo of {pg["title"]}: {artist}, {lic}, via Wikimedia Commons', 'real': True}


def wants(sb):
    """(scene, kind, query) the style asks for"""
    st = story.settings(sb).get('style', 'mixed')
    if st in ('graphics', '3d'): return []
    out = []
    for i, s in enumerate(sb['scenes']):
        ty = s['visual']['type']
        if ty == 'chart': continue
        if s.get('shots') and ty != 'person': continue                    # fetched shot by shot (fetch_shots)
        foot, photo = s.get('footage', ''), s.get('photo', '')
        if ty == 'person' and not photo: photo = s['visual'].get('name', '')
        if photo and ty in ('person', 'title', 'stamp', 'quote'): out.append((i, 'real', photo, foot))
        elif foot and (st == 'documentary' or ty in ('title', 'stamp', 'date', 'list', 'versus', 'person')): out.append((i, 'stock', foot, ''))
        elif st == 'documentary' and foot: out.append((i, 'stock', foot, ''))
    return out[:16]


MAX_SHOTS = 48


def fetch_shots(job, sb, got, used):
    """one clip (or photo) per spoken phrase: scene i -> got[i]['shots'] = [{file, kind, words}]. Scenes are fetched 4 at a time."""
    if story.settings(sb).get('style', 'mixed') in ('graphics', '3d'): return
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock, n = threading.Lock(), [0]

    def take(m):
        with lock:
            if m['id'] in used: return False
            used.add(m['id']); return True

    def scene(i, sc):
        shots = sc.get('shots') or []
        out, credits = [], []
        for k, sh in enumerate(shots):
            with lock:
                if n[0] >= MAX_SHOTS: break
            q = sh.get('q', '')
            try:
                done = None
                for qq in dict.fromkeys([q, sh.get('words', '')]):             # the search, then the spoken words themselves
                    for m in pixabay_videos(qq, used):
                        if not take(m): continue
                        f = f'media/{i}_s{k}.mp4'
                        try: get(m['url'], os.path.join(job, f))
                        except Exception: continue
                        if not _clip_ok(os.path.join(job, f)): continue
                        if _vision_ok(os.path.join(job, f), 'video', sh.get('words', ''), qq) is not False: done = (m, f); break   # can't judge (quota) = keep; the frames are checked before sending
                    if done: break
                if not done and story.settings(sb).get('style') != 'documentary':   # no video matched: a real photo instead (documentary = moving footage only, owner Nov 9)
                    m = pixabay_photo(q, used)
                    if m and take(m):
                        f = f'media/{i}_s{k}.jpg'; get(m['url'], os.path.join(job, f))
                        if _vision_ok(os.path.join(job, f), 'photo', sh.get('words', ''), q) is True: done = (m, f)
                if not done: print('shot: no match for', i, k, q); continue
                m, f = done
                with lock: n[0] += 1
                out.append({'file': f, 'kind': m['kind'], 'words': sh.get('words', ''), 'q': q}); credits.append(m['credit'])
                print('shot', i, k, m['kind'], q)
            except Exception as e:
                print('shot fail', i, k, q, repr(e)[:100])
        if out:
            if got.get(str(i), {}).get('real'):                                # real photo of the person/company stays (round portrait); footage goes behind it
                got[str(i)]['shots'] = out; got[str(i)]['credit'] += ' · ' + ' · '.join(sorted(set(credits)))
            else:
                got[str(i)] = {'kind': out[0]['kind'], 'file': out[0]['file'], 'credit': ' · '.join(sorted(set(credits))), 'real': False, 'q': shots[0].get('q', ''), 'shots': out}

    todo = [(i, sc) for i, sc in enumerate(sb['scenes']) if sc.get('shots') and sc['visual']['type'] != 'chart']
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda a: scene(*a), todo))

def fetch(job):
    sb = json.load(open(os.path.join(job, 'storyboard.json')))
    os.makedirs(os.path.join(job, 'media'), exist_ok=True)
    got, used = {}, set()
    for i, kind, q, alt in wants(sb):
        m = None
        try:
            if kind == 'real':
                m = wiki_photo(q)
                if m and sb['scenes'][i]['visual']['type'] == 'person':          # a person's photo must come from THEIR page (not their company's logo)
                    name = [w.lower() for w in re.findall(r'[A-Za-z]{3,}', q)]
                    title = m['credit'].split(':')[0].lower()
                    if not any(w in title for w in name[-1:]) or 'logo' in m.get('id', '').lower():
                        print('photo is not of', q, '->', m['credit'][:60]); m = None
                if not m and alt: kind, q = 'stock', alt
            if kind == 'stock':
                m = pixabay_video(q, used) or pixabay_photo(q, used)
            if not m: print('media: nothing for', i, q); continue
            ext = '.mp4' if m['kind'] == 'video' else '.jpg'
            f = f'media/{i}{ext}'
            try:
                get(m['url'], os.path.join(job, f))
            except ValueError:                                            # too big: take the smaller rendition
                if not m.get('small'): raise
                get(m['small'], os.path.join(job, f))
            used.add(m['id'])
            if m['kind'] == 'video' and not _clip_ok(os.path.join(job, f)):        # broken or motionless clip: a photo instead
                m = pixabay_photo(q, used) if kind == 'stock' else None
                if not m: continue
                f = f'media/{i}.jpg'; get(m['url'], os.path.join(job, f)); used.add(m['id'])
            got[str(i)] = {'kind': m['kind'], 'file': f, 'credit': m['credit'], 'real': bool(m.get('real')), 'q': q}
            if m['kind'] == 'video' and kind == 'stock':                  # fast cuts: a few more moving clips for the same scene
                more = []
                for k in range(1, 4):
                    try:
                        x = pixabay_video(q, used)
                        if not x: break
                        ff = f'media/{i}_{k}.mp4'
                        get(x.get('small') or x['url'], os.path.join(job, ff))
                        used.add(x['id'])
                        if not _clip_ok(os.path.join(job, ff)): continue
                        more.append(ff)
                        if x['credit'] not in got[str(i)]['credit']: got[str(i)]['credit'] += ' · ' + x['credit']
                    except Exception as e:
                        print('extra clip fail', i, k, repr(e)[:80]); break
                if more: got[str(i)]['more'] = more
            print('media', i, m['kind'], q, '->', m['credit'])
        except Exception as e:
            print('media fail', i, q, repr(e)[:120])
    fetch_shots(job, sb, got, used)
    json.dump(got, open(os.path.join(job, 'media.json'), 'w'), indent=1)
    return got


def credits(job):
    p = os.path.join(job, 'media.json')
    if not os.path.exists(p): return ''
    cr = sorted({m['credit'] for m in json.load(open(p)).values()})
    return ('\n\nFootage & photos: ' + ' · '.join(cr)) if cr else ''


if __name__ == '__main__':
    fetch(sys.argv[1])
