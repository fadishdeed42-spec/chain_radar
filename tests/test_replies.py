"""Step 2: reply quality. Run: python3 tests/run.py"""
from helpers import *
import replies, brain, time, random


def test_numbers_rejects_invented_and_accepts_rounding():
    post = 'Strategy bought 4,300,000,000 dollars of bitcoin, up 12% this week'
    assert replies.numbers_ok('That is $4.3B in one buy.', post)[0]
    assert replies.numbers_ok('Up 12% already.', post)[0]
    ok, miss = replies.numbers_ok('That is 80% more than last year.', post)
    assert not ok and '80%' in miss
    assert not replies.numbers_ok('They now hold 640k BTC.', post)[0]
    assert replies.numbers_ok('Two of them did it, nine times.', post)[0]          # small counts are fine


def test_shape_rules():
    assert replies.shape_ok('The detail that matters is the custody setup, not the headline number itself.')[0]
    for bad in ('too short', 'This is bro level stuff and honestly it is great news for everybody today', 'Read more at https://x.com/a now please friends',
                'Great point #bitcoin and many more words follow here', 'Let that sink in, because this one matters a great deal today',
                'A reply with an em dash — that should fail the shape check here'):
        assert not replies.shape_ok(bad)[0], bad


def test_age_note():
    now = 10000.0
    assert replies.age_note({'ts': now - 300}, now).startswith('🟢')
    assert replies.age_note({'ts': now - 3600}, now).startswith('🟡')
    assert replies.age_note({'ts': now - 3 * 3600}, now).startswith('🔴')
    assert replies.age_note({}, now) == ''


def test_choose_n_best_three_different_angles():
    mk = lambda st, r, ok=True: {'style': st, 'reply': r, 'nums_ok': ok, 'shape_ok': True}
    c = [mk('a', 'one'), mk('a', 'one b'), mk('b', 'two'), mk('c', 'three'), mk('d', 'four', False), mk('e', 'five')]
    v = {'c': [{'n': 1, 'unsupported': [], 'human': 9, 'value': 9}, {'n': 2, 'unsupported': [], 'human': 8, 'value': 8},
               {'n': 3, 'unsupported': ['invented'], 'human': 9, 'value': 9}, {'n': 4, 'unsupported': [], 'human': 5, 'value': 5},
               {'n': 6, 'unsupported': [], 'human': 7, 'value': 7}]}
    out, lvl = replies.choose_n(c, v, 3)
    assert [x['reply'] for x in out] == ['one', 'five', 'three'] and lvl == 'verified'         # one per angle, unsupported + bad-number drafts dropped
    out, lvl = replies.choose_n(c, None, 3)                                                     # judge down: labelled honestly
    assert len(out) == 3 and lvl == 'numbers'
    assert replies.choose_n([mk('x', 'y', False)], None) == ([], None)


def test_pick_styles_new_ideas_come_from_unused_angles():
    first = replies.pick_styles((), 3)
    nxt = replies.pick_styles(first, 3)
    assert len(set(first)) == 3 and not set(first) & set(nxt)


def test_reply_ideas_with_stubbed_ai():
    r = radar()
    post = 'Strategy bought 4,300,000,000 dollars of bitcoin this week.'

    def fake(prompt):
        if 'strict fact-checker' in prompt:
            return {'c': [{'n': i, 'unsupported': [], 'human': 8, 'value': 8} for i in range(1, 6)]}
        return {'replies': [{'style': 'numbers', 'reply': 'That is $4.3B in a single week, a pace few buyers can match.'},
                            {'style': 'detail', 'reply': 'They also hold 900k coins now, a record by far, apparently.'},
                            {'style': 'question', 'reply': 'Who is selling to them at these prices, and why now?'},
                            {'style': 'calm_take', 'reply': 'Big buy, but one week does not make a trend by itself.'},
                            {'style': 'light_humor', 'reply': 'Somebody really did not want to wait for the dip.'}], 'symbol': 'BTC', 'chart': False}
    r.gemini_json = fake; r.live_data = lambda t: ('', None)
    out = r.reply_ideas(post, 'someone')
    assert out and len(out['ideas']) == 3 and out['level'] == 'verified'
    assert not any('900k' in c['reply'] for c in out['ideas'])                                 # the invented number never gets through


def test_reply_ideas_fail_closed():
    r = radar()
    r.gemini_json = lambda p: {'replies': [{'style': 'numbers', 'reply': 'Up 77% since the dip, which is wild for such a big move.'}]}
    r.live_data = lambda t: ('', None)
    assert r.reply_ideas('Bitcoin moved today.', 'x') is None
