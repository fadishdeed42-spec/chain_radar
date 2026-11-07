import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'studio'))
import qc

def sb(lines): return {'scenes': [{'line': l, 'role': 'hook' if i == 0 else 'setup'} for i, l in enumerate(lines)], 'est_secs': 38}

def test_weak_hook_and_unsupported_number_fail():
    r = qc.script(sb(['This is the story of a hack.', 'They stole $9.9 billion in 2024.']), 'In 2024 hackers stole $1.5 billion from Bybit.')
    lv = {(x['area'], x['level']) for x in r}
    assert ('hook', 'fail') in lv and ('facts', 'fail') in lv and qc.verdict(r) == 'fail'

def test_good_script_passes_facts_and_loop():
    r = qc.script(sb(['$1.5 billion. Gone in minutes.', 'Bybit was hacked in 2024.', 'And the $1.5 billion never came back.']), 'In 2024 hackers stole $1.5 billion from Bybit.')
    lv = {x['area']: x['level'] for x in r}
    assert lv['hook'] == 'ok' and lv['facts'] == 'ok' and lv['loop'] == 'ok'

def test_skip_is_never_reported_as_passed():
    rep = qc.report([qc.it(qc.SKIP, 'visual', 'not reviewed'), qc.it(qc.OK, 'format', 'fine')], 'Video')
    assert 'not reviewed' in rep and 'could not run' in rep.split('\n')[0]
