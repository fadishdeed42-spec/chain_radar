"""/card: research -> facts-only spec -> real chart -> tall image with Approve / Fix / Redo; an invented number is flagged."""
import time
from helpers import radar

FACTS = ('On March 23, 2022 attackers drained 173,600 ETH and 25.5 million USDC from the Ronin bridge, about $625 million. '
         '5 of 9 validator keys were compromised. The hack was discovered on March 29, 2022, 6 days later. ') * 3
SPEC = {'title': '$625 million stolen. Nobody noticed for 6 days.', 'tag': 'March 2022 · Ronin bridge',
        'stats': [{'value': '$625M', 'label': 'stolen', 'color': 'red'}, {'value': '6 days', 'label': 'unnoticed'}, {'value': '5 of 9', 'label': 'keys hacked'}],
        'story': ['They drained 173,600 ETH.', '!Nobody noticed until March 29.'], 'lesson': 'Keys are only as safe as people.',
        'question': 'Would you open the PDF?', 'post_text': '$625M stolen and nobody noticed for 6 days.', 'coin': 'AXS', 'event_date': '2022-03-29', 'chart_label': 'Mar 29: revealed'}


def _setup(spec):
    r = radar(); sent = []
    r.tg = lambda text, photo=None, buttons=None: sent.append((text, photo, buttons))
    r.short_facts = lambda topic: FACTS
    r.gemini_json = lambda prompt, strong=False: dict(spec)
    t0 = time.mktime((2022, 3, 9, 0, 0, 0, 0, 0, 0))
    r.binance = lambda sym, gran, start=None, end=None, limit=500: [((t0 + i * 86400) * 1000, 50, 52, 48, 50 + i % 3, 1) for i in range(41)]
    return r, sent


def test_card_ok():
    r, sent = _setup(SPEC); tgs = {}
    r.card_make('Ronin bridge hack', tgs)
    text, photo, btns = sent[-1]
    assert photo and photo[:2] == b'\xff\xd8', 'no image'
    assert '✅ Every number' in text and 'AXS price' in text, text
    assert [b[1][:4] for b in btns] == ['lca:', 'lcf:', 'lcr:']


def test_card_flags_invented_number():
    bad = dict(SPEC, story=['They drained 999,999 ETH.'])
    r, sent = _setup(bad); r.card_make('Ronin bridge hack', {})
    assert '❌' in sent[-1][0] and '999999' in sent[-1][0], sent[-1][0]
