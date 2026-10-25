"""Chain Radar Shorts brain: learns what makes crypto / money YouTube Shorts go viral.

collect():        YouTube Data API (free key) -> crypto & finance Shorts with views, likes, length and the channel's
                  normal views per video. outlier = views / channel average: the real measure of a winner, independent
                  of how big the channel is.
analyze_batch():  Gemini watches winners AND flops from their YouTube link and records the hook (first words), hook type,
                  jokes, pacing, tone, ending, and why it worked or failed.
patterns():       what winners have that flops don't (numbers, length, loop endings, hook types...).
Everything is saved in state/shorts.json (committed by the bot) so it keeps growing.
Quota: ~16 searches (1,600 units) + a few cheap stats calls a day, far under YouTube's free 10,000 units/day.
"""
import json, os, re, threading, time
from datetime import datetime, timezone, timedelta

import requests

YT = os.environ.get('YOUTUBE_API_KEY', '')
GEM = os.environ.get('GEMINI_API_KEY', '')
FILE = 'state/shorts.json'
LOCK = threading.RLock()
API = 'https://www.googleapis.com/youtube/v3/'

QUERIES = ['bitcoin story', 'crypto story', 'crypto scam story', 'crypto hack', 'bitcoin history', 'crypto explained',
           'bitcoin facts', 'crypto news', 'ethereum story', 'crypto billionaire', 'crypto crash', 'money story',
           'satoshi nakamoto', 'crypto mystery', 'ftx collapse', 'bitcoin pizza', 'memecoin', 'crypto fraud',
           'stock market story', 'finance facts', 'rich people facts', 'scam exposed']
HOOK_TYPES = ['shocking number', 'question', 'bold claim', 'mystery / secret', 'story opening', 'conflict / villain',
              'warning', 'contrarian', 'list', 'other']
_D = None


def load():
    global _D
    with LOCK:
        if _D is None:
            try:
                _D = json.load(open(FILE))
            except Exception:
                _D = {}
            _D.setdefault('v', {}); _D.setdefault('ch', {}); _D.setdefault('q', 0); _D.setdefault('quota', {})
        return _D


def save():
    with LOCK:
        d = load(); now = time.time()
        d['v'] = {k: v for k, v in d['v'].items() if now - v['seen'] < 120 * 86400}
        os.makedirs('state', exist_ok=True)
        json.dump(d, open(FILE + '.tmp', 'w'), separators=(',', ':')); os.replace(FILE + '.tmp', FILE)


def _get(path, **params):
    try:
        r = requests.get(API + path, params={**params, 'key': YT}, timeout=15)
        if not r.ok:
            print('youtube', path, r.status_code, r.text[:160].replace('\n', ' '))
            return {}
        return r.json()
    except Exception as e:
        print('youtube fail', path, repr(e)[:80]); return {}


def _secs(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0) if m else 0


def _spend(units):
    d = load(); day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    d['quota'] = {day: d['quota'].get(day, 0) + units}
    return d['quota'][day]


def collect(n_queries=16):
    """One daily pass: a rotating set of searches -> Shorts stats -> channel averages -> outlier scores."""
    if not YT:
        print('shorts: no YOUTUBE_API_KEY'); return 0
    d = load(); now = time.time()
    qs = [QUERIES[(d['q'] + i) % len(QUERIES)] for i in range(n_queries)]
    d['q'] = (d['q'] + n_queries) % len(QUERIES)
    after = (datetime.now(timezone.utc) - timedelta(days=60)).strftime('%Y-%m-%dT%H:%M:%SZ')
    ids = set()
    for n, q in enumerate(qs):                                           # mix most-viewed and relevant: winners AND flops
        j = _get('search', part='id', q=q + ' #shorts', type='video', videoDuration='short', order='viewCount' if n % 2 == 0 else 'relevance',
                 publishedAfter=after, maxResults=50, relevanceLanguage='en')
        _spend(100)
        if not j and n == 0:
            print('shorts: YouTube search failed, stopping (check the key)'); return 0
        ids |= {it['id']['videoId'] for it in j.get('items', []) if it.get('id', {}).get('videoId')}
    ids = list(ids)
    new, chans = 0, set()
    for i in range(0, len(ids), 50):                                     # stats: 1 unit per 50 videos
        j = _get('videos', part='snippet,statistics,contentDetails', id=','.join(ids[i:i + 50])); _spend(1)
        for v in j.get('items', []):
            dur = _secs(v['contentDetails'].get('duration'))
            if not 8 <= dur <= 75 or (v['snippet'].get('defaultAudioLanguage') or 'en')[:2] not in ('en', ''):
                continue
            st, sn = v.get('statistics', {}), v['snippet']
            rec = d['v'].get(v['id'], {})
            if not rec:
                new += 1
            rec.update({'t': sn['title'][:150], 'ch': sn['channelId'], 'cht': sn.get('channelTitle', '')[:60], 'dur': dur,
                        'pub': sn['publishedAt'], 'views': int(st.get('viewCount', 0)), 'likes': int(st.get('likeCount', 0)),
                        'com': int(st.get('commentCount', 0)), 'desc': (sn.get('description') or '')[:300],
                        'tags': (sn.get('tags') or [])[:12], 'seen': now})
            d['v'][v['id']] = rec; chans.add(sn['channelId'])
    need = [c for c in chans if now - d['ch'].get(c, {}).get('t', 0) > 7 * 86400]
    for i in range(0, len(need), 50):                                    # channel size + normal views per video
        j = _get('channels', part='statistics', id=','.join(need[i:i + 50])); _spend(1)
        for c in j.get('items', []):
            st = c.get('statistics', {})
            vc = max(1, int(st.get('videoCount', 1)))
            d['ch'][c['id']] = {'subs': int(st.get('subscriberCount', 0) or 0), 'avg': int(st.get('viewCount', 0)) / vc, 't': now}
    score_all()
    save()
    print(f'shorts collected: {len(ids)} found, {new} new, total {len(d["v"])}, quota today {list(d["quota"].values())[0]}')
    return new


def score_all():
    d = load()
    for v in d['v'].values():
        c = d['ch'].get(v['ch'])
        if c and c['avg'] > 0:
            v['out'] = round(v['views'] / c['avg'], 2)                   # 5.0 = five times the channel's normal
            v['subs'] = c['subs']
        v['lr'] = round(v['likes'] / max(1, v['views']), 4)


# ---------------------------------------------------------------- Gemini watches the Short
ANALYZE = ('You are analyzing a YouTube Short to learn what makes Shorts go viral. Watch it and reply with ONLY a JSON object:\n'
           '{"hook": "exact words spoken (or shown) in the first 3 seconds",\n'
           ' "hook_type": one of ' + json.dumps(HOOK_TYPES) + ',\n'
           ' "number_in_hook": true/false, "hook_seconds": seconds until the main promise is clear,\n'
           ' "tone": one of ["funny","serious","mystery","hype","educational"],\n'
           ' "jokes": number of jokes or funny beats, "words_per_sec": estimated speaking speed,\n'
           ' "twist": true/false (is there a reveal or twist?), "twist_second": second of the twist or null,\n'
           ' "ending": one of ["loop","cta","cliffhanger","plain"],\n'
           ' "visual": one sentence on the visual style (captions, charts, stock footage, face, memes...),\n'
           ' "voice": "AI" or "human" plus one word for delivery,\n'
           ' "transcript": first 60 words of the narration,\n'
           ' "why": one sentence: the main reason this Short works or fails}')


def gemini_video(vid, models):
    url = f'https://www.youtube.com/watch?v={vid}'
    for m in models:
        try:
            r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent', params={'key': GEM}, timeout=90,
                              json={'contents': [{'parts': [{'file_data': {'file_uri': url}}, {'text': ANALYZE}]}],
                                    'generationConfig': {'temperature': 0.2, 'response_mime_type': 'application/json'}})
            if r.ok:
                txt = ''.join(p.get('text', '') for p in r.json()['candidates'][0]['content']['parts'] if not p.get('thought'))
                return json.loads(re.search(r'\{.*\}', txt, re.S).group(0))
            print('gemini video', m, r.status_code, r.text[:140].replace('\n', ' '))
            if r.status_code in (400, 403):
                continue
        except Exception as e:
            print('gemini video fail', m, repr(e)[:100])
    return None


def analyze_batch(n, models):
    """Watch the clearest winners and clearest flops not analyzed yet (balanced, so the model learns the difference)."""
    if not GEM or not models:
        return 0
    d = load()
    todo = [(k, v) for k, v in d['v'].items() if 'an' not in v and v.get('out') is not None and v['views'] >= 2000]
    win = sorted([x for x in todo if x[1]['out'] >= 3], key=lambda x: -x[1]['out'])[:n // 2]
    flop = sorted([x for x in todo if x[1]['out'] <= 0.5], key=lambda x: x[1]['out'])[:n // 2]
    done = 0
    for k, v in win + flop:
        a = gemini_video(k, models)
        with LOCK:
            v['an'] = a or {'fail': 1}
        done += bool(a)
        if done % 10 == 0:
            save()
        time.sleep(4)                                                    # stay under free-tier rate limits
    save()
    print(f'shorts analyzed: {done} of {len(win) + len(flop)}')
    return done


# ---------------------------------------------------------------- what the data says
def winners(days=60, k=10):
    d = load(); cut = datetime.now(timezone.utc) - timedelta(days=days)
    vs = [(vid, v) for vid, v in d['v'].items() if v.get('out') and v['views'] >= 20000
          and datetime.fromisoformat(v['pub'].replace('Z', '+00:00')) >= cut]
    return sorted(vs, key=lambda x: -x[1]['out'])[:k]


def best_hooks(k=30):
    d = load()
    hs = [(v['out'], v['an']['hook'], v['an'].get('hook_type', ''), v['views']) for v in d['v'].values()
          if v.get('an', {}).get('hook') and v.get('out', 0) >= 3]
    return sorted(hs, key=lambda x: -x[0])[:k]


def patterns():
    """Compare analyzed winners (5x+ their channel) vs flops (under half their channel)."""
    d = load()
    an = [v for v in d['v'].values() if v.get('an') and not v['an'].get('fail')]
    W = [v for v in an if v.get('out', 0) >= 3]; F = [v for v in an if v.get('out', 9) <= 0.5]
    if len(W) < 8 or len(F) < 8:
        return None

    def share(g, f):
        return sum(1 for v in g if f(v)) / len(g) * 100

    def avg(g, f):
        xs = [f(v) for v in g if isinstance(f(v), (int, float))]
        return sum(xs) / len(xs) if xs else 0
    rows = [('Number in the hook', share(W, lambda v: v['an'].get('number_in_hook') is True), share(F, lambda v: v['an'].get('number_in_hook') is True), '%'),
            ('Has a twist', share(W, lambda v: v['an'].get('twist') is True), share(F, lambda v: v['an'].get('twist') is True), '%'),
            ('Loop ending', share(W, lambda v: v['an'].get('ending') == 'loop'), share(F, lambda v: v['an'].get('ending') == 'loop'), '%'),
            ('Length (sec)', avg(W, lambda v: v['dur']), avg(F, lambda v: v['dur']), 's'),
            ('Promise clear by (sec)', avg(W, lambda v: v['an'].get('hook_seconds')), avg(F, lambda v: v['an'].get('hook_seconds')), 's'),
            ('Jokes', avg(W, lambda v: v['an'].get('jokes')), avg(F, lambda v: v['an'].get('jokes')), ''),
            ('Words / sec', avg(W, lambda v: v['an'].get('words_per_sec')), avg(F, lambda v: v['an'].get('words_per_sec')), '')]
    types = {}
    for v in W:
        t = v['an'].get('hook_type', 'other'); types[t] = types.get(t, 0) + 1
    return {'n_w': len(W), 'n_f': len(F), 'rows': rows, 'types': sorted(types.items(), key=lambda x: -x[1])[:4]}


def status():
    d = load()
    an = [v for v in d['v'].values() if v.get('an') and not v['an'].get('fail')]
    return {'shorts': len(d['v']), 'channels': len(d['ch']), 'analyzed': len(an),
            'winners': sum(1 for v in d['v'].values() if v.get('out', 0) >= 3), 'quota': d.get('quota', {})}
