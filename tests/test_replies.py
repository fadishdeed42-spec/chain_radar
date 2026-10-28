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


def test_choose_picks_best_and_drops_unsupported():
    c = [{'style': 'a', 'reply': 'one', 'nums_ok': True, 'shape_ok': True}, {'style': 'b', 'reply': 'two', 'nums_ok': True, 'shape_ok': True},
         {'style': 'c', 'reply': 'three', 'nums_ok': False, 'shape_ok': True}]
    v = {'c': [{'n': 1, 'unsupported': ['invented name'], 'human': 9, 'value': 9, 'stance_fit': 9},
               {'n': 2, 'unsupported': [], 'human': 6, 'value': 6, 'stance_fit': 6}]}
    best, lvl = replies.choose(c, v)
    assert best['reply'] == 'two' and lvl == 'verified'
    best, lvl = replies.choose(c, None)                                      # judge down: numbers/shape only, labelled honestly
    assert best['reply'] == 'one' and lvl == 'numbers'
    assert replies.choose([c[2]], None) == (None, None)


def test_pick_styles_prefers_what_worked():
    stats = {'detail': (50, 50)}
    rnd = random.Random(1); n = 0
    for _ in range(1000):
        n += 'detail' in replies.pick_styles(stats, n=1, rnd=rnd)
    assert n > 1000 * .21                                                    # uniform would be 1/6 = 17%
    assert len(set(replies.pick_styles({}, n=3))) == 3


def test_best_reply_with_stubbed_ai():
    r = radar()
    post = 'Strategy bought 4,300,000,000 dollars of bitcoin this week.'
    calls = []

    def fake(prompt):
        calls.append(prompt)
        if 'strict fact-checker' in prompt:
            return {'c': [{'n': 1, 'unsupported': [], 'human': 8, 'value': 8, 'stance_fit': 8}]}
        return {'replies': [{'style': 'numbers', 'reply': 'That is $4.3B in a single week, a pace few buyers can match.'},
                            {'style': 'detail', 'reply': 'They also hold 900k coins now, a record by far.'}], 'symbol': 'BTC', 'chart': False}
    r.gemini_json = fake; r.live_data = lambda t: ('', None)
    out = r.best_reply(post, 'someone', None, 'neutral')
    assert out and out['reply'].startswith('That is $4.3B') and out['level'] == 'verified'
    judged = [c for c in calls if 'strict fact-checker' in c][0]
    assert '900k' not in judged                                              # the invented-number draft never reaches the judge


def test_best_reply_fails_closed():
    r = radar()
    r.gemini_json = lambda p: {'replies': [{'style': 'numbers', 'reply': 'Up 77% since the dip, which is wild for such a big move.'}], 'symbol': 'NONE', 'chart': False}
    r.live_data = lambda t: ('', None)
    assert r.best_reply('Bitcoin moved today.', 'x', None, 'neutral') is None


def test_brain_reply_stats_and_linking():
    brain.load()['replies'] = []
    now = time.time()
    brain.reply_add({'rid': 'a1', 't': now, 'key': 'k', 'author': 'x', 'style': 'detail', 'stance': 'agree', 'reply': 'The custody detail is the part that really matters here', 'coin': None, 'chart': False, 'check': 'verified', 'age_min': 5})
    brain.reply_add({'rid': 'a2', 't': now, 'key': 'k', 'author': 'x', 'style': 'question', 'stance': 'agree', 'reply': 'Who holds the keys for all of that coin supply anyway', 'coin': None, 'chart': False, 'check': 'verified', 'age_min': 5})
    brain.reply_mark('a1', 'outcome', 1); brain.reply_mark('a2', 'outcome', -1)
    assert brain.reply_stats() == {'detail': (1, 1), 'question': (0, 1)}
    got = brain.reply_link('The custody detail is the part that really matters here friends', 'https://x.com/me/status/1', now)
    assert got and got['rid'] == 'a1' and got['url'].endswith('/1')
    assert brain.reply_link('totally unrelated words about something else entirely', 'https://x.com/me/status/2', now) is None
    brain.load()['replies'] = []
