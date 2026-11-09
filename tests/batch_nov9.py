"""Hand-written, fact-checked storyboard for Nov 9 2026 (new standard). Sources: Elliptic (updated Nov 9 2026), TRM Labs (Nov 3 2026).
python tests/batch_nov9.py  -> jobs/<jid>/storyboard.json + autorender/hold flags"""
import os, sys, json, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'studio')); os.chdir(ROOT)
import story, qc

NFA = '\n\nNot financial advice. Entertainment and education only.'
def sc(role, emo, line, hit, visual):
    return {'role': role, 'emotion': emo, 'line': line, 'hit': hit, 'visual': visual, 'beats': [], 'shots': [], 'footage': '', 'photo': ''}

JOBS = {'t3700040': dict(
    title='North Korea Is Making Meme Coins… With Stolen Binance Money 🕵️', tone='mystery', theme='violet',
    chart={'symbol': 'BTC', 'start': '2026-10-15', 'end': '2026-11-09'},
    lesson='',
    description=("Oct 29, 2026: about $6.4 billion was stolen from Binance between 20:05 and 23:56 UTC. Investigators (Elliptic, TRM Labs) attribute it to North Korea. "
                 "About $2.85 billion has been frozen or seized; about $3 billion is still in linked wallets. The launderers now use more than 20,000 wallets on 16 blockchains. "
                 "Their newest trick: worthless meme tokens they create themselves and trade through liquidity pools, so funds never pass directly between wallets. "
                 "On NEAR, about 117,000 NEAR (~$430,000) went through six home-made tokens. After the 2025 Bybit hack, all 499,000 stolen ETH were laundered within ten days.\n\n"
                 "Sources: Elliptic, \"How North Korea is laundering the $6.4 billion stolen from Binance\" (updated Nov 9, 2026); TRM Labs, \"Binance Hack Update\" (Nov 3, 2026)." + NFA),
    hashtags='#Binance #NorthKorea #Crypto #MemeCoins #Hack #ChainSecrets #shorts',
    pinned='Would you check who created a coin before buying it? 👇',
    respell={'Bybit': 'Bye-bit', 'NEAR': 'Near'},
    scenes=[
        sc('hook', 'shock', 'North Korea is making its own meme coins. To hide stolen Binance money.', 'coins',
           {'type': 'title', 'text': 'MEME COINS', 'sub': 'made by North Korea', 'icon': 'token'}),
        sc('setup', 'tense', 'October 29. Hackers took $6.4 billion from Binance in under four hours.', 'billion',
           {'type': 'chart', 'date': '2026-10-29', 'label': 'OCT 29 · $6.4B TAKEN'}),
        sc('setup', 'tense', 'Investigators blame North Korea. About $2.85 billion was frozen in time.', 'frozen',
           {'type': 'versus', 'left': ['FROZEN', '$2.85B'], 'right': ['STILL HELD', '~$3B'], 'note': 'ELLIPTIC · NOV 9'}),
        sc('turn', 'dark', 'About $3 billion is still out there. Now they are moving it.', 'moving',
           {'type': 'flow', 'from': 'BINANCE LOOT', 'amount': '~$3B', 'to': ['ETH', 'BTC', 'TRON'], 'frozen': ''}),
        sc('turn', 'tense', 'Over 20,000 wallets. 16 blockchains.', 'wallets',
           {'type': 'counter', 'value': 20000, 'prefix': '', 'suffix': '+', 'label': 'WALLETS · 16 BLOCKCHAINS'}),
        sc('twist', 'shock', 'The newest trick: worthless meme coins they create themselves.', 'worthless',
           {'type': 'stamp', 'icon': 'token', 'label': 'HOME-MADE TOKENS', 'word': 'WORTHLESS', 'bad': True}),
        sc('twist', 'curious', 'They trade them through pools. The money never goes wallet to wallet.', 'pools',
           {'type': 'list', 'items': ['MAKE A COIN', 'TRADE IT IN A POOL', 'HARDER TO TRACE']}),
        sc('payoff', 'tense', 'On NEAR alone: six home-made tokens. About $430,000 pushed through.', 'tokens',
           {'type': 'counter', 'value': 430000, 'prefix': '$', 'suffix': '', 'label': 'THROUGH 6 TOKENS ON NEAR'}),
        sc('payoff', 'dark', 'They have done this before. After the Bybit hack, 499,000 ether vanished in ten days.', 'days',
           {'type': 'timer', 'text': '10 DAYS', 'label': 'BYBIT · 499,000 ETH LAUNDERED'}),
        sc('end', 'calm', 'So when a strange new coin appears overnight, ask who made it.', 'made',
           {'type': 'title', 'text': 'WHO MADE THIS COIN?', 'icon': 'question'}),
    ])}

def sh(*pairs):
    return [{'q': q, 'words': w} for q, w in pairs]

def scf(role, emo, line, hit, visual, shots):
    d = sc(role, emo, line, hit, visual); d['shots'] = shots; d['footage'] = shots[0]['q'] if shots else ''; return d

JOBS['t3700041'] = dict(JOBS['t3700040'], scenes=[
    scf('hook', 'shock', 'North Korea is making its own meme coins.', 'coins',
        {'type': 'title', 'text': 'MEME COINS', 'sub': 'made by North Korea', 'icon': 'token'},
        sh(('hacker typing code dark room', 'North Korea is making'), ('cryptocurrency coins gold', 'meme coins'))),
    scf('hook', 'tense', 'To hide stolen Binance money.', 'stolen',
        {'type': 'stamp', 'icon': 'cash', 'label': 'BINANCE MONEY', 'word': 'STOLEN', 'bad': True},
        sh(('money cash counting hands', 'To hide stolen Binance money'))),
    sc('setup', 'tense', 'October 29. Hackers took $6.4 billion from Binance in under four hours.', 'billion',
       {'type': 'chart', 'date': '2026-10-29', 'label': 'OCT 29 · $6.4B TAKEN'}),
    scf('setup', 'dark', 'Investigators blame North Korea.', 'korea',
        {'type': 'stamp', 'icon': 'officer', 'label': 'INVESTIGATORS BLAME', 'word': 'NORTH KOREA', 'bad': True},
        sh(('north korea flag', 'Investigators blame North Korea'))),
    scf('setup', 'tense', 'About $2.85 billion was frozen in time.', 'frozen',
        {'type': 'counter', 'value': 2850000000, 'prefix': '$', 'suffix': '', 'label': 'FROZEN IN TIME'},
        sh(('bank vault door', 'About $2.85 billion was frozen'))),
    scf('turn', 'dark', 'About $3 billion is still out there. Now they are moving it.', 'moving',
        {'type': 'flow', 'from': 'STILL HELD', 'amount': '~$3B', 'to': ['ETH', 'BTC', 'TRON'], 'frozen': ''},
        sh(('digital network data flow', 'About $3 billion'), ('server room lights', 'Now they are moving it'))),
    scf('turn', 'tense', 'Over 20,000 wallets. 16 blockchains.', 'wallets',
        {'type': 'counter', 'value': 20000, 'prefix': '', 'suffix': '+', 'label': 'WALLETS · 16 BLOCKCHAINS'},
        sh(('blockchain network', 'Over 20,000 wallets'))),
    scf('twist', 'shock', 'The newest trick: worthless meme coins they create themselves.', 'worthless',
        {'type': 'stamp', 'icon': 'token', 'label': 'HOME-MADE TOKENS', 'word': 'WORTHLESS', 'bad': True},
        sh(('bitcoin coins', 'The newest trick'), ('computer code screen', 'they create themselves'))),
    scf('twist', 'curious', 'They trade them through pools. The money never goes wallet to wallet.', 'pools',
        {'type': 'list', 'items': ['MAKE A COIN', 'TRADE IT IN A POOL', 'HARDER TO TRACE']},
        sh(('stock trading screen', 'They trade them through pools'), ('phone crypto app', 'The money never goes'))),
    scf('payoff', 'tense', 'On NEAR alone: six home-made tokens. About $430,000 pushed through.', 'tokens',
        {'type': 'counter', 'value': 430000, 'prefix': '$', 'suffix': '', 'label': 'THROUGH 6 TOKENS ON NEAR'},
        sh(('crypto trading chart', 'On NEAR alone'), ('money transfer digital', 'About $430,000'))),
    scf('payoff', 'dark', 'They have done this before.', 'before',
        {'type': 'title', 'text': 'NOT THE FIRST TIME', 'sub': 'Bybit, 2025'},
        sh(('hacker hoodie computer night', 'They have done this before'))),
    scf('payoff', 'dark', 'After the Bybit hack, 499,000 ether vanished in ten days.', 'days',
        {'type': 'timer', 'text': '10 DAYS', 'label': 'BYBIT · 499,000 ETH LAUNDERED'},
        sh(('ethereum coin', 'After the Bybit hack'))),
    scf('end', 'calm', 'So when a strange new coin appears overnight, ask who made it.', 'made',
        {'type': 'title', 'text': 'WHO MADE THIS COIN?', 'icon': 'question'},
        sh(('person looking at phone at night', 'So when a strange new coin appears overnight'))),
])

if __name__ == '__main__':
    for jid in sys.argv[1:] or list(JOBS):
        j = dict(JOBS[jid])
        sb = {k: j[k] for k in ('title', 'tone', 'theme', 'chart', 'lesson', 'description', 'hashtags', 'pinned', 'respell', 'scenes')}
        sb.update({'length': 60, 'settings': {'length': 60, 'style': 'documentary' if jid >= 't3700041' else 'graphics', 'autorender': True, 'chart': 'on'}})
        for k, s in enumerate(sb['scenes']):
            assert s['hit'].lower() in re.sub(r'[^\w\s]', ' ', s['line'].lower()).split(), (jid, k, s['hit'])
        assert not qc.standard(sb), qc.standard(sb)
        chk, probs = story.check(json.loads(json.dumps(sb)), strict=False)
        print(jid, 'words', chk.get('words'), 'est', chk.get('est_secs'), 'ok', chk.get('length_ok'), probs)
        os.makedirs(f'jobs/{jid}', exist_ok=True)
        json.dump(sb, open(f'jobs/{jid}/storyboard.json', 'w'), indent=1, ensure_ascii=False)
        for f in ('autorender.flag', 'hold.flag'): open(f'jobs/{jid}/{f}', 'w').write('1')
        json.dump({'state': 'draft'}, open(f'jobs/{jid}/status.json', 'w'))
