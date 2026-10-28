"""Charts: only when the move is worth reacting to, and drawn from the real candles. Run: python3 tests/run.py"""
from helpers import *
import chart2, io


def rows(n, step_s, p0, p1, end=1_700_000_000):
    """a straight real-looking series from p0 to p1 ending at `end`"""
    out = []
    for i in range(n):
        o = p0 + (p1 - p0) * i / n; c = p0 + (p1 - p0) * (i + 1) / n
        out.append(((end - (n - 1 - i) * step_s) * 1000, o, max(o, c) * 1.002, min(o, c) * .998, c, 10.0))
    return out


def test_gate_thresholds():
    flat = {'24h': rows(96, 900, 100, 100.1), '7d': rows(168, 3600, 100, 101), '30d': rows(120, 21600, 100, 130), '60d': rows(60, 86400, 100, 150)}
    assert chart2.worth_it(flat) is None                                   # SOL +0.1% today, +30% a month: nobody reacts
    assert chart2.worth_it({**flat, '24h': rows(96, 900, 100, 110.5)})['key'] == '24h'
    assert chart2.worth_it({**flat, '24h': rows(96, 900, 100, 89)})['key'] == '24h'          # -11% counts too
    assert chart2.worth_it({**flat, '7d': rows(168, 3600, 100, 111)})['key'] == '7d'
    assert chart2.worth_it({**flat, '30d': rows(120, 21600, 100, 205)})['key'] == '30d'      # doubled in a month
    assert chart2.worth_it({**flat, '60d': rows(60, 86400, 100, 49)})['key'] == '60d'        # halved in two months
    assert chart2.worth_it({**flat, '24h': rows(96, 900, 100, 109)}) is None                 # 9% a day is not enough
    assert chart2.worth_it({}) is None


def test_render_is_a_1080x1350_png_with_the_real_move():
    from PIL import Image
    r = rows(96, 900, 100, 112)
    img, mv = chart2.render('Solana', 'SOL', r, 'in 24 hours', 'Binance', 'MOVER', event_ms=r[40][0], event_label='ETF NEWS')
    im = Image.open(io.BytesIO(img))
    assert im.size == (1080, 1350) and abs(mv - 0.12) < .001                 # hero = first open -> last close, computed from the same candles
    img2, mv2 = chart2.render('X', 'X', rows(168, 3600, 100, 60), 'in 7 days', 'Coinbase')
    assert mv2 < -.39 and len(img2) > 20000                                  # area-line variant for long windows


def test_coin_view_explains_instead_of_charting_a_small_move():
    r = radar(); sent = []
    r.tg = lambda text, photo=None, buttons=None: sent.append((text, photo, buttons)); r.unack = lambda: None
    coin = {'id': 'solana', 'sym': 'SOL', 'name': 'Solana', 'price': 100.0, 'h1': 0, 'h24': .1, 'rank': 5}
    r.resolve_coin = lambda q: coin
    r.candles = lambda c, span, ev=None: ((rows(96, 900, 100, 100.1) if span == '1d' else rows(168, 3600, 100, 101) if span == '7d' else
                                           rows(120, 21600, 100, 120) if span == '30d' else rows(60, 86400, 100, 130)), 'Binance', span)
    r.coin_view('sol', {})
    assert len(sent) == 1 and sent[0][1] is None and 'not a move people will react to' in sent[0][0] and '+0.1% in 24 hours' in sent[0][0]
    assert sent[0][2] and sent[0][2][0][1] == 'c:solana:1d'                  # an explicit "show it anyway" button


def test_event_chart_hero_is_the_move_after_the_news():
    import card
    r = rows(60, 86400, 10000, 6000, end=1_584_000_000)
    img, mv = card.chart_card('Black Thursday', {'name': 'Bitcoin', 'sym': 'BTC'}, r, 'daily candles', 'TRUE STORY', 'Binance', event_ms=r[30][0])
    assert -.30 < mv < -.20 and len(img) > 20000                 # open of the news candle -> lowest low after it
