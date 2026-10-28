"""Post looks: every look renders a 1080x1350 PNG from real text only. Run: python3 tests/run.py"""
from helpers import *
import re
import io, looks
from PIL import Image


def test_every_look_renders():
    for k, f in looks.LOOKS.items():
        for title, kf in (('Bybit hacked for $1.5 billion in the biggest crypto theft ever recorded', 'Attackers drained cold-wallet funds in a day.'), ('Pizza day', ''),
                          ('A' * 40 + ' ' + 'long ' * 60, 'x ' * 150)):
            im = Image.open(io.BytesIO(f(title, kf, 'CoinDesk')))
            assert im.size == (1080, 1350), (k, title[:20])


def test_no_fake_numbers_or_claims_in_looks():
    src = open(os.path.join(ROOT, 'looks.py')).read()
    assert 'verified' not in src.lower().replace('# ', '') or 'sources verified' not in src       # the terminal must not claim verification it did not do
    assert not re.search(r'\d+(\.\d)?[KkMm] (likes|reposts|views)', src)


def test_default_look_and_buttons():
    r = radar()
    assert r.default_look('HACK', 'x') == 'TERMINAL' and r.default_look('TRUE STORY', 'x') == 'CASEFILE' and r.default_look('BREAKING', 'x') == 'BREAKING'
    o = [v for _, v in r.options({'title': 'x'}, {'title': 'x'}, None)]
    assert {'BREAKING', 'CASEFILE', 'POSTCARD', 'GLASS', 'TERMINAL', 'HEADLINE'} <= set(o)
    img = r.build_image({'title': 'Some story', 'tag': 'TRUE STORY', 'visual': 'HEADLINE', 'keyfact': 'k'}, {'src': 's'}, 'facts', None, 'CASEFILE')
    assert Image.open(io.BytesIO(img)).size == (1080, 1350)


def test_viral_picks_one_best_story_with_reasons():
    r = radar(); sent = []
    r.tg = lambda text, photo=None, buttons=None: sent.append((text, buttons)); r.git_sync = lambda *a, **k: None
    st = {'menu': {'a': {'title': 'Bitcoin ETF sees record inflows as banks pile in', 'src': 'CoinDesk', 'tag': 'BREAKING'},
                   'b': {'title': 'Small thing happens on a chain', 'src': 'X', 'tag': 'BREAKING'}},
          'top': [['b', 50, 0.2, 1], ['a', 80, 0.5, 3]], 'probs': {'a': 0.7, 'b': 0.3}}
    r.load_state = lambda: st
    r.cmd_viral({})
    assert len(sent) == 1 and 'Bitcoin ETF' in sent[0][0] and 'Small thing' not in sent[0][0] and 'Confirmed by 3 sources' in sent[0][0]
    assert sent[0][1] == [('📝 Make post', 'p:a')]
    sent.clear(); st['top'] = []; r.cmd_viral({})
    assert 'Nothing strong' in sent[0][0]                                                  # honest when there is no good pick
