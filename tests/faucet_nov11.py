"""Bitcoin Faucet remake in the #25 graphics style (owner picked option A, Nov 11 2026).
Sources: Cointelegraph (19,700 BTC given away), bitcointalk faucet thread via Satoshi Nakamoto Institute (Satoshi's reply),
CoinGeek (June 2010 launch, 1,100 BTC of his own), CryptoPotato (first Mt. Gox trade $0.05, July 2010). Price: BTC ~$73.9k on Nov 11 2026."""
import os, sys, json, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'studio')); os.chdir(ROOT)
import story, qc

def sc(role, emo, line, hit, visual):
    return {'role': role, 'emotion': emo, 'line': line, 'hit': hit, 'visual': visual, 'beats': [], 'shots': [], 'footage': '', 'photo': ''}

JID = 't3700050'
SB = dict(
    title='In 2010, This Website Gave Away FREE Bitcoin 😳 (Now $1.4 Billion)', tone='hype', theme='gold',
    chart={'symbol': 'BTC', 'start': '2011-09-01', 'end': '2026-11-11'}, lesson='',
    description=("June 2010: programmer Gavin Andresen launched the \"Bitcoin Faucet\" - a website that gave 5 free bitcoin to anyone who solved a captcha.\n"
                 "He filled it with 1,100 of his own coins, and even Satoshi Nakamoto replied with tips to stop people claiming twice.\n"
                 "Back then, 5 bitcoin were worth less than a dollar. In total, the faucet gave away about 19,700 BTC.\n"
                 "Today that's over $1.4 billion - and one visitor's 5 free coins are worth over $360,000.\n\n"
                 "Would you have clicked? 👇\n\nNot financial advice. Entertainment and education only."),
    hashtags='#bitcoin #btc #crypto #cryptohistory #satoshi #shorts',
    pinned='Be honest: if you got 5 free bitcoin in 2010… would you still have them today? 👇',
    respell={'captcha': 'cap-cha', 'Andresen': 'Andreesen', '1,100': 'eleven hundred'},
    scenes=[
        sc('hook', 'shock', 'In 2010, a website gave away free bitcoin.', 'free',
           {'type': 'slam', 'text': 'FREE BITCOIN', 'sub': '2010'}),
        sc('hook', 'shock', 'Today, those coins are worth over a billion dollars.', 'billion',
           {'type': 'counter', 'value': 1400000000, 'prefix': '$', 'suffix': '+', 'label': 'WORTH TODAY', 'icon': 'bitcoin'}),
        sc('setup', 'curious', 'All you had to do was solve a captcha.', 'solve',
           {'type': 'app', 'app': 'BITCOIN FAUCET', 'title': 'Prove you are human', 'field': 'captcha', 'value': '✓ HUMAN', 'alert': '+5 BTC SENT'}),
        sc('setup', 'excited', 'Five bitcoin. Free. Every visitor.', 'free',
           {'type': 'counter', 'value': 5, 'prefix': '', 'suffix': ' BTC', 'label': 'FREE · EVERY VISITOR', 'icon': 'bitcoin'}),
        sc('setup', 'curious', 'It was called the Bitcoin Faucet.', 'faucet',
           {'type': 'title', 'text': 'THE BITCOIN FAUCET', 'sub': 'June 2010', 'icon': 'bitcoin'}),
        sc('setup', 'curious', 'A programmer named Gavin Andresen built it.', 'built',
           {'type': 'person', 'name': 'GAVIN ANDRESEN', 'role': 'PROGRAMMER', 'prop': 'laptop'}),
        sc('turn', 'excited', 'He filled it with 1,100 of his own coins.', 'own',
           {'type': 'counter', 'value': 1100, 'prefix': '', 'suffix': ' BTC', 'label': 'HIS OWN COINS', 'icon': 'bitcoin'}),
        sc('twist', 'shock', 'Even Satoshi Nakamoto replied, with tips to stop cheaters.', 'satoshi',
           {'type': 'title', 'text': 'SATOSHI REPLIED', 'sub': 'tips to stop cheaters', 'icon': 'question'}),
        sc('turn', 'curious', 'Back then, five bitcoin were worth less than a dollar.', 'less',
           {'type': 'versus', 'left': ['5 BTC', '2010'], 'right': ['UNDER $1', 'VALUE'], 'note': 'FIRST MT. GOX TRADE: $0.05'}),
        sc('payoff', 'excited', 'In total, it gave away about 19,700 bitcoin.', 'total',
           {'type': 'counter', 'value': 19700, 'prefix': '', 'suffix': ' BTC', 'label': 'GIVEN AWAY FOR FREE', 'icon': 'bitcoin'}),
        sc('payoff', 'shock', 'Today, that is over $1.4 billion.', 'billion',
           {'type': 'chart', 'date': '2026-11-11', 'label': 'TODAY · $1.4B+'}),
        sc('payoff', 'shock', 'Those five free coins? Over $360,000.', 'free',
           {'type': 'counter', 'value': 360000, 'prefix': '$', 'suffix': '+', 'label': '5 FREE COINS TODAY', 'icon': 'cash'}),
        sc('end', 'calm', 'Why give it away? He wanted people to try it.', 'try',
           {'type': 'title', 'text': 'SO PEOPLE COULD TRY IT', 'icon': 'bitcoin'}),
        sc('end', 'curious', 'Would you have clicked?', 'clicked',
           {'type': 'title', 'text': 'WOULD YOU HAVE CLICKED?', 'icon': 'question'}),
    ])

if __name__ == '__main__':
    sb = dict(SB)
    sb.update({'length': 50, 'settings': {'length': 50, 'style': 'graphics', 'autorender': True, 'chart': 'on', 'energy': 'high',
                                           'pace': 'fast', 'motion': 'strong', 'captions': 'key', 'music': 'off', 'whoosh': 'off'}})
    for k, s in enumerate(sb['scenes']):
        assert s['hit'].lower() in re.sub(r'[^\w\s]', ' ', s['line'].lower()).split(), (k, s['hit'])
    print('standard', qc.standard(sb))
    chk, probs = story.check(json.loads(json.dumps(sb)), strict=False)
    print('words', chk.get('words'), 'est', chk.get('est_secs'), 'ok', chk.get('length_ok'), probs)
    print('settings after check', chk.get('settings') if isinstance(chk, dict) else '')
    vj, _ = story.voice_job(story.check(json.loads(json.dumps(sb)), strict=False)[0])
    print('voice cfg', vj['cfg'], [x[1] for x in vj['scenes']]); print([x[0] for x in vj['scenes']])
    os.makedirs(f'jobs/{JID}', exist_ok=True)
    json.dump(sb, open(f'jobs/{JID}/storyboard.json', 'w'), indent=1, ensure_ascii=False)
    for f in ('autorender.flag', 'hold.flag'): open(f'jobs/{JID}/{f}', 'w').write('1')
    json.dump({'state': 'draft'}, open(f'jobs/{JID}/status.json', 'w'))
