"""End-to-end test job: real facts -> storyboard -> length fit -> fact-check polish -> jobs/<jid>/ (+ autorender flag).
python tests/make_job.py "topic" 45 jid   (needs GEMINI keys; run by .github/workflows/studio_test.yml)"""
import sys, os, json
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'studio'))
os.chdir(ROOT)
import radar as r, story

topic, L, jid = sys.argv[1], int(sys.argv[2]), sys.argv[3]
sett = {'length': max(60, L), 'style': 'documentary', 'autorender': True}
facts = r.short_facts(topic)
best = None
for attempt in range(2):
    raw = r.make_storyboard(topic, facts, None, None, L, 'auto', sett)
    if not isinstance(raw, dict): continue
    raw['settings'] = dict(sett)
    try:
        cand, _ = r.draft_check(raw)
    except ValueError as e:
        print('invalid', e); continue
    cand = r.fit_length(cand, facts)
    cand = r.story_pass(cand, facts)
    cand, left = r.polish_script(cand, facts)
    r.verify_quotes(cand, facts); r.verify_receipts(cand, facts); r.label_check(cand, facts)
    cand['review'] = {str(k): v[:2] for k, v in left.items()}
    print('attempt', attempt, 'words', cand['words'], 'ok', cand.get('length_ok'), 'flags', len(left), 'filler', r.filler_hits(cand))
    if best is None or (len(left), abs(cand['words'] - cand['target_words'])) < (len(best['review']), abs(best['words'] - best['target_words'])):
        best = cand
    if cand.get('length_ok') and not left: break
assert best, 'no script'
r.save_job(jid, best, 'draft')
open(f'jobs/{jid}/autorender.flag', 'w').write('1')
open(f'jobs/{jid}/hold.flag', 'w').write('1')                       # test videos wait for review before they are sent
lines = '%0A'.join(f'{i}. {x["line"]}' for i, x in enumerate(best['scenes'], 1)).replace('%', '%25').replace('%250A', '%0A')
print(f'::notice title=script {jid} ({best["words"]} words, flags {len(best["review"])})::' + best.get('title', '') + '%0A' + lines + '%0Aflags: ' + json.dumps(best['review'])[:600])
print('respell', best.get('respell'))
