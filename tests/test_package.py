"""Step 3: /story and /today packages, removed commands, /menu toggles. Run: python3 tests/run.py"""
from helpers import *
import time

FACTS = ('On March 12, 2020: Black Thursday: Bitcoin crashes about 40% in a day.\n- Mar 12, 2020: Bitcoin falls below $4,000 as markets panic (Reuters)')
GOOD = ['Bitcoin lost about 40% in a single day. Here is how.', 'On March 12, 2020 it fell below $4,000 as markets panicked.', 'Panic selling hit every market at once.',
        'Leverage unwound and exchanges struggled to keep up.', 'The lesson: no asset is a safe haven on the worst day. Full story in 40s 👇']


def fake_radar(posts, judge=None):
    r = radar(); calls = []

    def gj(p):
        calls.append(p)
        if 'strict fact-checker' in p:
            return judge if judge is not None else {'p': [{'n': i + 1, 'unsupported': []} for i in range(len(posts))]}
        return {'title': 'Black Thursday', 'posts': posts, 'symbol': 'NONE', 'event_date': 'NONE', 'chart_title': 'x'}
    r.gemini_json = gj
    return r, calls


def test_package_accepts_supported_thread():
    r, _ = fake_radar(GOOD)
    pk = r.build_package('Black Thursday', FACTS, [])
    assert pk and len(pk['posts']) == 5 and not pk['flags'] and pk['checked'] == 'full'     # "Full story in 40s" is not flagged as an invented number


def test_package_retries_then_flags_invented_numbers():
    bad = GOOD[:1] + ['Bitcoin then rebounded 87% within a week.'] + GOOD[2:]
    r, calls = fake_radar(bad)
    pk = r.build_package('Black Thursday', FACTS, [])
    assert pk and 2 in pk['flags'] and 'numbers' in pk['flags'][2]                          # never silently accepted: it is flagged for you
    assert sum('strict fact-checker' not in c for c in calls) == 2                          # one retry with the reason


def test_package_flags_unsupported_claims_from_the_judge():
    r, _ = fake_radar(GOOD, {'p': [{'n': 3, 'unsupported': ['Lehman Brothers collapsed first']}]})
    pk = r.build_package('Black Thursday', FACTS, [])
    assert 3 in pk['flags']


def test_package_fails_closed_without_enough_posts():
    r, _ = fake_radar(GOOD[:2])
    assert r.build_package('x', FACTS, []) is None


def test_removed_commands_and_features():
    r = radar(); sent = []
    r.tg = lambda text, photo=None, buttons=None: sent.append((text, buttons))
    r.save_tg = lambda t: None; r.CHAT = ''; tgs = {'menu': {}}
    for cmd in ('/movers', '/hacks', '/kit', '/hook x', '/menu', '/brain'):
        sent.clear(); r.handle({'message': {'text': cmd, 'from': {'id': 1}}}, tgs)
        assert sent and sent[0][0] == r.HELP, cmd                                           # unknown now -> help text, not the old feature
    sent.clear(); r.handle({'message': {'text': 'Some pasted news article text that is long enough to have been turned into a post before ' * 2, 'from': {'id': 1}}}, tgs)
    assert sent and sent[0][0] == r.HELP                                                    # pasted articles / forwards no longer make posts
    names = [c for c, _ in r.COMMANDS]
    assert not {'movers', 'hacks', 'kit', 'hook', 'chart', 'menu', 'brain'} & set(names) and {'story', 'today', 'top', 'short', 'viral'} <= set(names)
    assert not hasattr(r, 'track_mine') and not hasattr(r, 'check_mine') and not hasattr(r, 'weekly_report') and not hasattr(r, 'on_feedback')


def test_scene_count_is_a_note_not_a_failure():
    r = radar(); sb = storyboard('a55db3fd'); sb['settings'] = {'length': 120}
    sb['scenes'] = sb['scenes'][:11]
    out, probs = r.draft_check(sb)
    assert any('scenes' in p for p in probs)


def test_judge_opinion_flags_are_dropped_but_invented_names_and_numbers_kept():
    r = radar()
    assert not r.concrete_unsupported('Global markets were already shaking', FACTS)
    assert not r.concrete_unsupported('the charts still look brutal', FACTS)
    assert r.concrete_unsupported('Lehman Brothers collapsed first', FACTS)
    assert r.concrete_unsupported('fell 87 percent', FACTS)
    assert not r.concrete_unsupported('fell below $4,000', FACTS)
