"""Step 1: script length. Run: python3 tests/run.py"""
from helpers import *
import story


def test_window_matches_the_time_window():
    for L in (30, 45, 60, 90, 120):
        for cw in (3, 8):
            lo, hi, tgt = story.window(L, cw)
            assert lo < tgt < hi
            assert story.WIN_LO * L - 1.2 <= story.est_secs(lo, cw) <= story.WIN_LO * L + 1.2, (L, cw, story.est_secs(lo, cw))
            assert story.WIN_HI * L - 1.2 <= story.est_secs(hi, cw) <= story.WIN_HI * L + 1.2, (L, cw, story.est_secs(hi, cw))
            assert abs(story.est_secs(tgt, cw) - L) < 1.5


def test_measured_rate_from_real_voices():
    rates = [story.measured_rate(d) for d in glob.glob(os.path.join(ROOT, 'jobs', '*'))]
    rates = [r for r in rates if r]
    assert rates and all(2.1 <= r <= 2.9 for r in rates), rates


def test_cz_script_is_no_longer_accepted_as_two_minutes():
    """the real case: 243 spoken words ran 1:40 for a '2 min' pick and used to pass"""
    sb = storyboard('a55db3fd')
    sb2, probs = story.check(sb, strict=False)
    assert sb2['length_ok'] is False and 'about 1:' in sb2['length_msg'] and any('script is about' in p for p in probs)
    try:
        story.check(storyboard('a55db3fd'), strict=True)
    except ValueError as e:
        assert str(e).startswith('script is')
    else:
        raise AssertionError('strict check must reject it')


def test_script_at_target_passes_and_estimate_is_close():
    for L in (60, 120):
        sb = storyboard('a55db3fd'); sb['length'] = L
        sb['scenes'] = (sb['scenes'] * 2)[:{60: 10, 120: 16}[L]]
        tgt = story.window(L, 8)[2]
        out, probs = story.check(spoken_target(sb, tgt), strict=False)
        assert out['length_ok'] is True and not any('script is' in p for p in probs), (out['words'], tgt)
        assert abs(out['est_secs'] - L) <= 2


def test_too_long_is_flagged_and_absurd_is_rejected():
    out, _ = story.check(spoken_target(storyboard('a55db3fd'), 330), strict=False)     # 20% over a 2:00 pick: flagged, repairable
    assert out['length_ok'] is False and 'about 2:' in out['length_msg']
    try:
        story.check(spoken_target(storyboard('a55db3fd'), 420), strict=False)           # 3:00 for a 2:00 pick: not repairable, rewrite
    except ValueError as e:
        assert str(e).startswith('script is')
    else:
        raise AssertionError('420 words must be rejected')


def test_outline_is_never_stored():
    sb = storyboard('a55db3fd'); sb['outline'] = ['x']
    out, _ = story.check(sb, strict=False)
    assert 'outline' not in out


def test_fit_length_expands_with_a_stubbed_model():
    r = radar()
    sb, _ = story.check(storyboard('a55db3fd'), strict=False)
    assert not sb['length_ok']
    short_total = sum(len(s['line'].split()) for s in sb['scenes'])
    want = round(sb['target_words'] / (sb['words'] / short_total))
    calls = []

    def fake(prompt):
        calls.append(prompt)
        n = len(sb['scenes'])
        return {'lines': [{'n': i + 1, 'line': ' '.join(sb['scenes'][i]['line'].split() + ['and'] * ((want - short_total) // n + 1))} for i in range(n)]}
    r.gemini_json = fake
    out = r.fit_length(sb, 'facts')
    assert calls and 'ADD about' in calls[0]
    assert out['length_ok'] is True, (out['words'], out['target_words'])


def test_fit_length_failure_is_reported_not_hidden():
    r = radar()
    sb, _ = story.check(storyboard('a55db3fd'), strict=False)
    r.gemini_json = lambda prompt: None                                # the model is down
    out = r.fit_length(sb, 'facts')
    assert out['length_ok'] is False and out['length_msg']             # returned as-is, flagged; the caller blocks the voice


def test_draft_check_repairs_length_only():
    r = radar()
    out, _ = r.draft_check(storyboard('a55db3fd'))                     # strict would raise for length; draft_check lets fit_length repair it
    assert out['length_ok'] is False
