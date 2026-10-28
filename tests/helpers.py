"""Shared test setup: import radar offline (no tokens, no network), a real storyboard to work with."""
import os, sys, json, types, glob
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'studio'))
os.environ.setdefault('TELEGRAM_TOKEN', 'x'); os.environ.setdefault('TELEGRAM_CHAT_ID', '1'); os.environ.setdefault('GEMINI_API_KEY', 'x')
try:
    import feedparser  # noqa
except ImportError:                                                    # not installed in some sandboxes: the logic under test does not use it
    sys.modules['feedparser'] = types.ModuleType('feedparser')


def radar():
    import radar as r
    return r


def storyboard(jid='a55db3fd'):
    return json.load(open(os.path.join(ROOT, 'jobs', jid, 'storyboard.json')))


def lines_with_words(sb, total_written):
    """same scenes, lines resized to about total_written written words (filler is neutral)"""
    sb = json.loads(json.dumps(sb)); n = len(sb['scenes']); per, extra = divmod(total_written, n)
    for i, s in enumerate(sb['scenes']):
        w = per + (1 if i < extra else 0)
        base = s['line'].split()[:w]
        while len(base) < w:
            base.append('steadily')
        s['line'] = ' '.join(base)
    return sb


def spoken_target(sb, target):
    """resize the lines until the SPOKEN word count (numbers expand) is the target"""
    import story
    total = target
    for _ in range(12):
        out = lines_with_words(sb, total)
        got = story.check(json.loads(json.dumps(out)), strict=False)[0]['words']
        if abs(got - target) <= 1:
            return out
        total += target - got
    return out
