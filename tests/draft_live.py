"""Live script test on GitHub (no Telegram): python3 tests/draft_live.py "topic" 45  -> prints the script the bot would send + the standard check."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['TELEGRAM_TOKEN'] = ''
import radar as r
r.tg = lambda text, photo=None, buttons=None: print('\n[TG]', __import__('re').sub(r'<[^>]+>', '', text)[:3500], '\n[buttons]', [b[0] for b in buttons or []])
r.save_job = r.studio_index = r.git_sync = r.studio_button = lambda *a, **k: None
r.ack = r.unack = lambda *a, **k: None
topic, length = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 45
tgs = {}
r.short_draft(topic, tgs, length=length)
for jid, d in tgs.get('shorts', {}).items():
    sb = d['sb']
    print('\n==== FINAL SCRIPT', jid, sb.get('title'), sb.get('tone'), sb.get('est_secs'))
    for i, s in enumerate(sb['scenes'], 1): print(f'{i}. {s["line"]}')
    import qc
    print('\nSTANDARD:', qc.standard(sb) or 'PASS'); print('REVIEW:', sb.get('review'))
    os.makedirs('out', exist_ok=True); json.dump(d, open(f'out/{jid}.json', 'w'), indent=1, default=str)
