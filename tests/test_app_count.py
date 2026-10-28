"""The Studio app counts spoken words in JS. It must agree with the bot (story.plan_line), or the app's green tick lies."""
from helpers import *
import story, subprocess, re

SAMPLES = ['In 2013, a poker game changed everything.', 'He sold his apartment for $900,000 to buy Bitcoin.', 'Binance paid a $4.3B fine, then $50M more.',
           'Prices fell 54% in 3.4x volume by Oct 25 2017.', 'The FBI and SEC froze 80,000 BTC worth $1.5 billion.', 'It lost $19,666 in the 1990s and 25th in 2021.',
           'Mt. Gox vs the U.S. in 2014: 850,000 BTC, 24/7.', 'Zhao paid $15 million. Then $5 million reward, again.', 'Founded in 2005, up 40K to 3.36B by 2009.']


def js_counts(lines, respell):
    src = open(os.path.join(ROOT, 'docs', 'studio', 'index.html')).read()
    a, b = src.index('const iw = n =>'), src.index('function estimate()')
    harness = ('const S = {words: %s, sb: {respell: %s}};\n' % (open(os.path.join(ROOT, 'docs', 'studio', 'words.json')).read(), json.dumps(respell))
               + src[a:b] + '\nconst L = %s; console.log(JSON.stringify(L.map(spokenCount)));' % json.dumps(lines))
    out = subprocess.run(['node', '-e', harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-400:]
    return json.loads(out.stdout)


def test_words_json_is_fresh():
    assert json.load(open(os.path.join(ROOT, 'docs', 'studio', 'words.json'))) == json.loads(json.dumps(story.app_tables(), sort_keys=True)), \
        'run: python3 studio/story.py'


def test_app_matches_bot_on_real_scripts_and_samples():
    lines, resp = [], {}
    for f in glob.glob(os.path.join(ROOT, 'jobs', '*', 'storyboard.json')):
        sb = json.load(open(f)); resp.update(sb.get('respell') or {})
        lines += [s['line'] for s in sb['scenes']]
    lines += SAMPLES
    js = js_counts(lines, resp)
    py = [sum(len(sp) for _, sp in story.plan_line(l, resp)) for l in lines]
    bad = [(l[:60], j, p) for l, j, p in zip(lines, js, py) if j != p]
    assert sum(js) == sum(py) or abs(sum(js) - sum(py)) / sum(py) < .015, (sum(js), sum(py))
    assert len(bad) <= max(2, len(lines) // 20), bad                  # at most ~5% of lines off by a word
