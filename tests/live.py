"""Live checks against the real AI (manual workflow: tests.yml). Prints a result table; exits 1 if a check fails.
python tests/live.py length"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import *
import builtins, atexit
_buf = []; _orig_print = builtins.print


def _print(*a, **k):                      # the runner's log download is blocked here, so also publish the whole output as ONE annotation (readable through the API)
    _orig_print(*a, **k); _buf.append(' '.join(str(x) for x in a))


builtins.print = _print
atexit.register(lambda: _orig_print('::notice title=live-result::' + '\n'.join(_buf)[:30000].replace('%', '%25').replace('\r', '').replace('\n', '%0A')))
import story, replies
from datetime import datetime, timezone


def live_length():
    r = radar()
    cases = [('Mt Gox collapse', 120), ('Silk Road founder Ross Ulbricht', 120), ('The Bitcoin pizza day', 60), ('FTX collapse', 90), ('The DAO hack', 45), ('QuadrigaCX', 30)]
    ok_n = 0
    print(f'rate used: {story.rate()} w/s\n{"topic":36} {"pick":>5} {"words":>6} {"est":>6} {"ok":>3} {"gemini calls":>12}')
    for topic, L in cases:
        calls = [0]; g0 = r.gemini_json
        def counted(p, g0=g0, calls=calls):
            calls[0] += 1; return g0(p)
        r.gemini_json = counted
        facts = r.short_facts(topic)
        best = None
        for attempt in range(2):
            raw = r.make_storyboard(topic, facts, None, None, L, 'auto', {})
            if not isinstance(raw, dict): continue
            raw['settings'] = {'length': L}
            try:
                cand, _ = r.draft_check(raw)
            except ValueError as e:
                print('   invalid:', str(e)[:90]); continue
            cand = r.fit_length(cand, facts)
            if best is None or abs(cand['words'] - cand['target_words']) < abs(best['words'] - best['target_words']): best = cand
            if cand.get('length_ok'): break
        r.gemini_json = g0
        if not best:
            print(f'{topic:36} {L:>5}   no script'); continue
        ok_n += bool(best.get('length_ok'))
        print(f'{topic:36} {story.mmss(L):>5} {best["words"]:>6} {story.mmss(best["est_secs"]):>6} {"yes" if best.get("length_ok") else "NO":>3} {calls[0]:>12}')
        if best['scenes']: print('     hook:', best['scenes'][0]['line'][:100])
    print(f'\n{ok_n}/{len(cases)} landed inside the length window without the user having to do anything')
    return ok_n >= len(cases) - 1


def live_replies():
    r = radar()
    posts = [('WatcherGuru', 'JUST IN: Strategy buys 4,200 BTC for $487 million, bringing total holdings to 640,000 BTC.'),
             ('zachxbt', 'A wallet linked to the Bybit hack just moved 10,000 ETH through a mixer.'),
             ('CoinDesk', 'Ethereum ETFs saw net inflows of $120 million yesterday, the fifth straight day.')]
    ok = 0
    for author, text in posts:
        out = None
        try:
            out = r.best_reply(text, author, None, 'neutral')
        except Exception as e:
            print('error', repr(e)[:120])
        if out:
            good, miss = replies.numbers_ok(out['reply'], text, out['live']); shape = replies.shape_ok(out['reply'])[0]
            ok += good and shape
            print(f'[{out["level"]}] ({out["style"]}) {out["reply"]}  | numbers ok={good} shape ok={shape}')
        else:
            print('NO REPLY (failed closed):', text[:60])
    print(f'{ok}/{len(posts)} replies passed every check')
    return ok >= 2


def emit_image(name, png_bytes):
    """the runner logs are unreadable from here, so a small JPEG goes out as one annotation (base64) and is decoded locally"""
    import io, base64
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert('RGB').resize((540, 675)); b = io.BytesIO(); im.save(b, 'JPEG', quality=62)
    _orig_print(f'::notice title=img-{name}::' + base64.b64encode(b.getvalue()).decode())


def live_chart():
    r = radar(); ok = True
    for cid in ('bitcoin', 'ethereum', 'solana', 'pepe'):
        coin = r.coin_by_id(cid)
        if not coin:
            print(cid, 'no coin data'); ok = False; continue
        g, summary = r.chart_gate(coin)
        print(f'{coin["sym"]:5} {fmt_(coin["price"])} | {summary} | gate: {g["key"] + " " + format(g["move"] * 100, "+.1f") + "%" if g else "no chart (not worth it)"}')
    coin = r.coin_by_id('bitcoin')
    rows, src, lab = r.candles(coin, '7d')
    print('BTC 7d candles', len(rows), src, '| first', rows[0][:5] if rows else None)
    if rows:
        img, mv = r.card.chart_card('Bitcoin last 7 days', coin, rows, lab, 'MOVER', src, focus=7 * 86400)
        print('7d chart move', round(mv * 100, 2), 'bytes', len(img)); emit_image('btc7d', img)
    img, why = r.hist_chart('BTC', datetime(2020, 3, 12, tzinfo=timezone.utc).timestamp(), 'Black Thursday')
    print('Black Thursday:', why, len(img) if img else None)
    if img: emit_image('blackthursday', img)
    # source agreement check for the same window
    b = r.binance('BTC', 86400, datetime(2020, 2, 20, tzinfo=timezone.utc).timestamp(), datetime(2020, 3, 20, tzinfo=timezone.utc).timestamp())
    c = r.coinbase('BTC', 86400, datetime(2020, 2, 20, tzinfo=timezone.utc).timestamp(), datetime(2020, 3, 20, tzinfo=timezone.utc).timestamp())
    cm = {x[0] // 86400000: x[4] for x in c or []}
    dev = sorted(abs(x[4] / cm[x[0] // 86400000] - 1) for x in b if x[0] // 86400000 in cm)
    print(f'binance {len(b)} candles, coinbase {len(c or [])} candles, median close difference {dev[len(dev) // 2] * 100:.2f}%' if dev else f'binance {len(b)} coinbase {len(c or [])} no overlap')
    return ok and bool(rows)


def fmt_(v):
    return f'${v:,.4g}'


def live_package():
    r = radar()
    facts = ('On March 12, 2020: Black Thursday: Bitcoin crashes about 40% in a day. (Well-documented crypto history.)\n'
             'Real headlines: Bitcoin falls below $4,000 as markets panic (Mar 12, 2020).')
    pk = r.build_package('Black Thursday', facts, [], datetime(2020, 3, 12, tzinfo=timezone.utc).timestamp())
    if not pk:
        print('no package'); return False
    for i, p in enumerate(pk['posts'], 1): print(i, len(p), p)
    print('flags', pk['flags'], '| checked', pk['checked'], '| chart:', pk['chart_note'], '| image bytes', len(pk['img']) if pk['img'] else None)
    return 5 <= len(pk['posts']) <= 7 and not pk['flags']


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    results = {}
    if what in ('length', 'all'): results['length'] = live_length()
    if what in ('replies', 'all'): results['replies'] = live_replies()
    if what in ('package', 'all'): results['package'] = live_package()
    if what in ('chart', 'all'): results['chart'] = live_chart()
    for k, v in results.items(): print(k, 'PASS' if v else 'FAIL')
    sys.exit(0 if all(results.values()) else 1)
