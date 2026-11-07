"""Which crypto / money Shorts go viral? YouTube Data API (free quota). Writes research/yt_formats.json"""
import os, json, re, requests, datetime as D
K = os.environ['YOUTUBE_API_KEY']; API = 'https://www.googleapis.com/youtube/v3/'
Q = ['crypto scam story', 'bitcoin story', 'crypto hack', 'bitcoin millionaire', 'crypto crash', 'bitcoin news today', 'crypto documentary',
     'money story', 'billionaire lost everything', 'biggest heist money', 'scammer caught', 'stock market crash story', 'how he made millions', 'ponzi scheme story']
after = (D.datetime.utcnow() - D.timedelta(days=180)).strftime('%Y-%m-%dT%H:%M:%SZ')
ids = {}
for q in Q:
    r = requests.get(API + 'search', params={'key': K, 'q': q, 'part': 'snippet', 'type': 'video', 'videoDuration': 'short', 'order': 'viewCount',
                                             'publishedAfter': after, 'maxResults': 25, 'relevanceLanguage': 'en'}, timeout=30).json()
    for x in r.get('items', []): ids.setdefault(x['id']['videoId'], q)
    print(q, len(r.get('items', [])), r.get('error', {}).get('message', ''))
vids = []
L = list(ids)
for i in range(0, len(L), 50):
    r = requests.get(API + 'videos', params={'key': K, 'id': ','.join(L[i:i + 50]), 'part': 'snippet,statistics,contentDetails'}, timeout=30).json()
    vids += r.get('items', [])
ch = {}
cids = list({v['snippet']['channelId'] for v in vids})
for i in range(0, len(cids), 50):
    r = requests.get(API + 'channels', params={'key': K, 'id': ','.join(cids[i:i + 50]), 'part': 'statistics,snippet'}, timeout=30).json()
    for c in r.get('items', []): ch[c['id']] = c
def secs(p):
    m = re.match(r'PT(?:(\d+)M)?(?:(\d+)S)?', p or ''); return int(m.group(1) or 0) * 60 + int(m.group(2) or 0) if m else 0
out = []
for v in vids:
    s = v['statistics']; c = ch.get(v['snippet']['channelId'], {})
    subs = int(c.get('statistics', {}).get('subscriberCount', 0) or 0); views = int(s.get('viewCount', 0))
    d = secs(v['contentDetails'].get('duration'))
    if d == 0 or d > 180: continue
    out.append({'q': ids[v['id']], 'id': v['id'], 'title': v['snippet']['title'], 'channel': v['snippet']['channelTitle'], 'subs': subs, 'views': views,
                'likes': int(s.get('likeCount', 0) or 0), 'comments': int(s.get('commentCount', 0) or 0), 'secs': d,
                'published': v['snippet']['publishedAt'][:10], 'ratio': round(views / max(subs, 1000), 1), 'desc': v['snippet'].get('description', '')[:160]})
out.sort(key=lambda x: -x['views'])
json.dump(out, open('research/yt_formats.json', 'w'), indent=0)
print('videos', len(out))
