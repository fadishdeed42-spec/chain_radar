"""Live checks against the real AI (manual workflow: tests.yml). Prints a result table; exits 1 if a check fails.
python tests/live.py length"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import *
import story


def live_length():
    r = radar()
    cases = [('Mt Gox collapse', 120), ('Silk Road founder Ross Ulbricht', 120), ('The Bitcoin pizza day', 60), ('FTX collapse', 90), ('The DAO hack', 45), ('QuadrigaCX', 30)]
    ok_n = 0
    print(f'rate used: {story.rate()} w/s\n{"topic":36} {"pick":>5} {"words":>6} {"est":>6} {"ok":>3} {"gemini calls":>12}')
    for topic, L in cases:
        calls = [0]; g0 = r.gemini_json
        def counted(p, g0=g0, calls=calls):
            calls[0] += 1; return g0(p)
        r.gemini_json = counted
        facts = r.short_facts(topic)
        best = None
        for attempt in range(2):
            raw = r.make_storyboard(topic, facts, None, None, L, 'auto', {})
            if not isinstance(raw, dict): continue
            raw['settings'] = {'length': L}
            try:
                cand, _ = r.draft_check(raw)
            except ValueError as e:
                print('   invalid:', str(e)[:90]); continue
            cand = r.fit_length(cand, facts)
            if best is None or abs(cand['words'] - cand['target_words']) < abs(best['words'] - best['target_words']): best = cand
            if cand.get('length_ok'): break
        r.gemini_json = g0
        if not best:
            print(f'{topic:36} {L:>5}   no script'); continue
        ok_n += bool(best.get('length_ok'))
        print(f'{topic:36} {story.mmss(L):>5} {best["words"]:>6} {story.mmss(best["est_secs"]):>6} {"yes" if best.get("length_ok") else "NO":>3} {calls[0]:>12}')
        if best['scenes']: print('     hook:', best['scenes'][0]['line'][:100])
    print(f'\n{ok_n}/{len(cases)} landed inside the length window without the user having to do anything')
    return ok_n >= len(cases) - 1


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    results = {}
    if what in ('length', 'all'): results['length'] = live_length()
    for k, v in results.items(): print(k, 'PASS' if v else 'FAIL')
    sys.exit(0 if all(results.values()) else 1)
