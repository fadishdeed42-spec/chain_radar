"""Pull candidate stock clips (Pixabay, free) for each scene: lab/stock/get.py QUERIES.json OUTDIR
QUERIES.json = [["query a", "query b"], ...] one list per scene. Saves sNN_k.mp4 (first 7 s, 1080 wide or tall) + sNN.jpg contact strip."""
import os, sys, json, subprocess, requests
KEY = os.environ['PIXABAY_API_KEY']; Q = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
used = set()
for i, qs in enumerate(Q):
    got = []
    for q in qs:
        r = requests.get('https://pixabay.com/api/videos/', params={'key': KEY, 'q': q, 'per_page': 20, 'safesearch': 'true'}, timeout=30)
        if not r.ok: print('err', q, r.status_code); continue
        for h in r.json().get('hits', []):
            if h['id'] in used or h.get('duration', 0) < 3: continue
            v = h['videos'].get('large') or {}
            if not v.get('url') or max(v.get('width', 0), v.get('height', 0)) < 1280: v = h['videos'].get('medium') or {}
            if not v.get('url'): continue
            used.add(h['id']); got.append((q, h['id'], v['url'], v.get('width'), v.get('height'), h.get('tags', '')))
            if sum(1 for g in got if g[0] == q) >= 3: break
        if len(got) >= 5: break
    strips = []
    for k, (q, hid, url, w, hh, tags) in enumerate(got[:5]):
        raw = f'/tmp/raw_{i}_{k}.mp4'; o = f'{OUT}/s{i:02d}_{k}.mp4'
        try:
            open(raw, 'wb').write(requests.get(url, timeout=120).content)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-t', '7', '-an', '-vf', 'scale=1920:1920:force_original_aspect_ratio=decrease', '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', o], check=True)
            j = f'/tmp/st_{i}_{k}.jpg'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', o, '-vf', "select='eq(n\\,10)+eq(n\\,90)',scale=-2:240,tile=2x1", '-frames:v', '1', j], check=True)
            strips.append(j); print(f's{i:02d}_{k}', hid, w, hh, q, '|', tags)
        except Exception as e: print('fail', i, k, e)
    if strips:
        subprocess.run(['ffmpeg', '-v', 'error', '-y'] + sum([['-i', s] for s in strips], []) + ['-filter_complex', f'vstack={len(strips)}' if len(strips) > 1 else 'null', f'{OUT}/s{i:02d}.jpg'])
