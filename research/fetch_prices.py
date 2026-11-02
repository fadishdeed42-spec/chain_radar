"""Real daily prices for the Trump-Iran long video: BTC (Bitstamp, Coinbase backup) and oil (FRED: WTI DCOILWTICO, Brent DCOILBRENTEU).
python research/fetch_prices.py 2026-02-01 -> research/prices.json"""
import sys, json, time, datetime, csv, io, requests
start = sys.argv[1] if len(sys.argv) > 1 else '2026-02-01'
s = int(datetime.datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).timestamp()); e = int(time.time())
out = {'fetched': datetime.datetime.utcnow().isoformat() + 'Z', 'btc': {}, 'btc_src': '', 'wti': {}, 'brent': {}}
d = lambda ts: datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%d')
try:
    a = s
    while a <= e:
        r = requests.get('https://www.bitstamp.net/api/v2/ohlc/btcusd/', params={'step': 86400, 'limit': 1000, 'start': a}, timeout=30).json()
        rows = r.get('data', {}).get('ohlc', [])
        if not rows: break
        for x in rows: out['btc'][d(int(x['timestamp']))] = {k: float(x[k]) for k in ('open', 'high', 'low', 'close')}
        a = max(int(x['timestamp']) for x in rows) + 86400
    out['btc_src'] = 'Bitstamp BTC/USD daily (UTC)'
except Exception as ex:
    print('bitstamp', ex)
for key, sid in (('wti', 'DCOILWTICO'), ('brent', 'DCOILBRENTEU')):
    try:
        t = requests.get(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}', timeout=30).text
        for row in csv.reader(io.StringIO(t)):
            if len(row) == 2 and row[0][:2] == '20' and row[1] not in ('.', ''):
                out[key][row[0]] = float(row[1])
        out[key + '_src'] = f'FRED {sid} (EIA spot price, daily)'
    except Exception as ex:
        print(sid, ex)
json.dump(out, open('research/prices.json', 'w'), indent=0)
print('btc days', len(out['btc']), 'wti days', len(out['wti']), 'brent days', len(out['brent']))
for k in ('btc', 'wti', 'brent'):
    ks = sorted(out[k]); print(k, ks[:1], ks[-1:])
