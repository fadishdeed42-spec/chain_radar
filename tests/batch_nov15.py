"""Stories 2-6 (Nov 15 2026), same style as Poly v2 (fast cuts, high energy) + a fact line under every picture.
Usage: python3 tests/batch_nov15.py doge|gox|genesis|split|satoshi
Sources:
 doge    - Wikipedia "Dogecoin" (Markus/Palmer, Dec 6 2013, Kabosu, Jamaican bobsled $36k in 2 days, NASCAR Mar 2014 ~$55k,
           Palmer left 2015, >$85B market cap May 2021, fell as much as 29.5% during Musk's SNL May 8 2021)
 gox     - The Block "What is Mt. Gox" (Magic: The Gathering Online eXchange, Jed McCaleb, 2010 Bitcoin exchange,
           sold to Karpeles Mar 2011, >70% of BTC transactions by early 2013, halted Feb 2014, ~850,000 BTC ~$450M, arrested Aug 2015)
 genesis - Bitcoin Wiki "Genesis block" (Jan 3 2009, The Times headline, 50 BTC unspendable, unknown if intentional, block 1 ~6 days later)
 split   - Bitcoin Magazine "Bitcoin Network Shaken by Blockchain Fork" + BIP 50 (Mar 11 2013, v0.8 LevelDB vs 0.7 BerkeleyDB locks,
           block 225430 >5,000 tx, Mt. Gox/BitPay paused deposits, -24%, pools downgraded, ~6 h, 24 blocks, $10,000 OKPay double spend)
 satoshi - Bitcoin.com / The Next Web / Tom's Hardware (last public post Dec 12 2010; Apr 23 2011 email to Mike Hearn; email to Gavin
           'mysterious shadowy figure' / 'pirate currency angle'; Gavin announced CIA talk Apr 27 2011; Gavin: 'The last email I sent him,
           I actually told him I was going to talk at the CIA'; believed to hold most of ~1.1M early BTC)"""
import os, sys, json, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'studio')); os.chdir(ROOT)
import story, qc


def sc(role, emo, line, hit, visual, fact='', slam=None, receipt=None):
    bt = []
    if slam:
        w, x = slam
        assert w in re.sub(r'[^\w\s]', ' ', line.lower()).split(), (line, w)
        bt = [{'word': w, 'text': x}]
    d = {'role': role, 'emotion': emo, 'line': line, 'hit': hit, 'visual': visual, 'beats': bt, 'shots': [], 'footage': '', 'photo': ''}
    if fact: d['fact'] = fact
    if receipt: d['receipt'] = receipt
    return d


END = lambda q: sc('end', 'curious', q, re.sub(r'[^\w]', ' ', q).split()[-1].lower(), {'type': 'versus', 'left': [q.split(' or ')[0].upper().rstrip('?'), '?'],
                   'right': [q.split(' or ')[1].upper().rstrip('?'), '?'], 'note': 'YOU DECIDE'}) if ' or ' in q else None
NFA = "\n\nNot financial advice. Entertainment and education only."

S = {}
S['doge'] = dict(jid='t3700071', num=31, title='A Joke Coin Hit $85 Billion 🐶 #Shorts', tone='funny', theme='gold',
    description=("Dogecoin started as a joke. In December 2013, Billy Markus and Jackson Palmer launched a coin with a Shiba Inu named Kabosu as its logo.\n"
                 "Fans raised $36,000 in two days to send Jamaica's bobsled team to the Winter Olympics, then sponsored a NASCAR car.\n"
                 "Palmer left crypto in 2015. In May 2021 the joke coin passed $85 billion - and during Elon Musk's SNL appearance it fell almost 30%.\n\n"
                 "Joke or genius? 👇" + NFA),
    hashtags='#Shorts #dogecoin #crypto #elonmusk #cryptohistory #doge', pinned='Joke or genius? Did you ever own any Doge? 👇',
    respell={'SNL': 'S N L', 'NASCAR': 'Nascar'},
    scenes=[
        sc('hook', 'shock', 'Two guys made a coin as a joke.', 'joke', {'type': 'slam', 'text': 'A JOKE COIN', 'sub': 'MADE IN 2013'}, fact='BILLY MARKUS + JACKSON PALMER'),
        sc('hook', 'shock', 'It grew to over eighty-five billion dollars.', 'billion', {'type': 'counter', 'value': 85000000000, 'prefix': '$', 'label': 'MARKET CAP · MAY 2021', 'icon': 'dogecoin'}, fact='OVER $85 BILLION'),
        sc('setup', 'calm', 'December 2013. Billy Markus and Jackson Palmer launched Dogecoin.', 'dogecoin', {'type': 'date', 'month': 'DEC', 'day': '6', 'event': 'DOGECOIN LAUNCHES'}, fact='DEC 6, 2013 · BASED ON LUCKYCOIN', slam=('launched', 'DOGECOIN')),
        sc('setup', 'excited', 'The logo? A Shiba Inu dog named Kabosu.', 'kabosu', {'type': 'title', 'text': 'KABOSU', 'sub': 'THE SHIBA INU ON THE COIN', 'icon': 'dogecoin'}, fact='THE "DOGE" MEME DOG'),
        sc('turn', 'excited', "Fans raised thirty-six thousand dollars in two days. For Jamaica's bobsled team.", 'bobsled',
           {'type': 'counter', 'value': 36000, 'prefix': '$', 'label': 'RAISED IN 2 DAYS', 'icon': 'cash'}, fact="JAMAICA'S BOBSLED TEAM · SOCHI 2014", slam=('bobsled', 'BOBSLED TEAM?!')),
        sc('turn', 'excited', 'Then they sponsored a NASCAR car.', 'car', {'type': 'title', 'text': 'A DOGE CAR', 'sub': 'NASCAR · 2014', 'icon': 'car'}, fact='ABOUT $55,000 IN DOGECOIN'),
        sc('twist', 'serious', 'In 2015, Jackson Palmer quit crypto.', 'quit', {'type': 'stamp', 'word': 'QUIT', 'label': 'CO-CREATOR LEAVES CRYPTO', 'icon': 'person', 'bad': True}, fact='JACKSON PALMER · 2015', slam=('quit', 'HE QUIT')),
        sc('turn', 'excited', 'Then 2021. Elon Musk kept tweeting about it.', 'tweeting', {'type': 'title', 'text': 'ELON MUSK', 'sub': 'TWEET AFTER TWEET', 'icon': 'phone'}, fact='2021 · DOGE GOES MAINSTREAM'),
        sc('payoff', 'shock', 'In May, the joke coin passed eighty-five billion dollars.', 'billion', {'type': 'counter', 'value': 85000000000, 'prefix': '$', 'label': 'A JOKE. WORTH THIS.', 'icon': 'dogecoin'}, fact='MAY 2021 · ALL-TIME HIGH', slam=('passed', 'TO THE MOON')),
        sc('twist', 'shock', 'Then Musk hosted Saturday Night Live.', 'live', {'type': 'title', 'text': 'SATURDAY NIGHT LIVE', 'sub': 'MAY 8, 2021'}, fact='THE "DOGEFATHER" ON TV'),
        sc('payoff', 'shock', 'During the show, it fell almost thirty percent.', 'percent', {'type': 'counter', 'value': 29.5, 'prefix': '-', 'suffix': '%', 'label': 'DURING THE SHOW', 'icon': 'fire'}, fact='DOWN TO ABOUT $0.49', slam=('fell', 'CRASH')),
        END('Joke or genius?'),
    ])

S['gox'] = dict(jid='t3700072', num=32, title='Bitcoin’s Biggest Exchange Started as a Card Game Site 🃏 #Shorts', tone='mystery', theme='crimson',
    description=("Mt. Gox stood for \"Magic: The Gathering Online eXchange\" - Jed McCaleb built it for trading game cards.\n"
                 "In 2010 he turned it into a Bitcoin exchange, and in March 2011 he sold it to Mark Karpelès.\n"
                 "By 2013 it handled over 70% of all Bitcoin transactions. In February 2014 trading stopped - about 850,000 Bitcoin were missing, "
                 "worth around $450 million at the time. Karpelès was arrested in 2015.\n\nWould you have trusted it? 👇" + NFA),
    hashtags='#Shorts #bitcoin #mtgox #crypto #cryptohistory', pinned='Would you have kept your Bitcoin on Mt. Gox? 👇',
    respell={'Mt.': 'Mount', 'Karpelès': 'Kar-puh-less', 'eXchange': 'exchange'},
    scenes=[
        sc('hook', 'shock', "Bitcoin's biggest exchange started as a card game website.", 'card', {'type': 'slam', 'text': 'A CARD GAME SITE', 'sub': "BECAME BITCOIN'S BIGGEST EXCHANGE"}, fact='MT. GOX'),
        sc('hook', 'shock', 'And it lost eight hundred fifty thousand Bitcoin.', 'lost', {'type': 'counter', 'value': 850000, 'suffix': ' BTC', 'label': 'MISSING', 'icon': 'bitcoin'}, fact='ABOUT $450 MILLION AT THE TIME'),
        sc('setup', 'curious', 'Mt. Gox meant Magic: The Gathering Online eXchange.', 'magic', {'type': 'title', 'text': 'M.T.G.O.X', 'sub': 'MAGIC: THE GATHERING ONLINE EXCHANGE'}, fact='THE NAME WAS A CARD GAME', slam=('magic', 'MAGIC CARDS')),
        sc('setup', 'calm', 'Jed McCaleb made it to trade game cards.', 'cards', {'type': 'person', 'name': 'JED McCALEB', 'role': 'FOUNDER', 'prop': 'laptop'}, fact='A FANTASY CARD TRADING SITE'),
        sc('turn', 'excited', 'In 2010, he turned it into a Bitcoin exchange.', 'exchange', {'type': 'title', 'text': 'BITCOIN EXCHANGE', 'sub': '2010', 'icon': 'bitcoin'}, fact='SAME NAME. NEW BUSINESS.', slam=('bitcoin', 'PIVOT')),
        sc('turn', 'serious', 'In March 2011, he sold it to Mark Karpelès.', 'sold', {'type': 'person', 'name': 'MARK KARPELÈS', 'role': 'NEW OWNER · 2011', 'prop': 'laptop'}, fact='MARCH 2011 · NEW OWNER'),
        sc('payoff', 'excited', 'By 2013, it handled over seventy percent of all Bitcoin transactions.', 'seventy', {'type': 'counter', 'value': 70, 'prefix': '>', 'suffix': '%', 'label': 'OF ALL BITCOIN TRANSACTIONS', 'icon': 'bitcoin'}, fact='THE BIGGEST IN THE WORLD', slam=('handled', 'NUMBER ONE')),
        sc('twist', 'shock', 'In February 2014, trading stopped.', 'stopped', {'type': 'stamp', 'word': 'HALTED', 'label': 'FEBRUARY 2014', 'icon': 'lock', 'bad': True}, fact='CUSTOMERS COULD NOT GET THEIR COINS OUT', slam=('trading', 'FROZEN')),
        sc('payoff', 'shock', 'Eight hundred fifty thousand Bitcoin were missing.', 'missing', {'type': 'counter', 'value': 850000, 'suffix': ' BTC', 'label': 'GONE', 'icon': 'skull'}, fact='ABOUT $450 MILLION AT THE TIME', slam=('missing', 'MISSING')),
        sc('turn', 'serious', 'Karpelès was arrested in 2015.', 'arrested', {'type': 'stamp', 'word': 'ARRESTED', 'label': 'AUGUST 2015 · JAPAN', 'icon': 'officer', 'bad': True}, fact='MARK KARPELÈS'),
        END('Trust or run?'),
    ])

S['genesis'] = dict(jid='t3700073', num=33, title='Satoshi Hid a Newspaper Headline in Bitcoin’s First Block 📰 #Shorts', tone='mystery', theme='gold',
    description=("January 3, 2009: Satoshi Nakamoto mined Bitcoin's first block - the genesis block.\n"
                 "Inside it he wrote a headline from The Times: \"Chancellor on brink of second bailout for banks.\" It proves the block "
                 "wasn't made before that day, and many read it as a message about the banks.\n"
                 "Its 50 Bitcoin reward can never be spent - a quirk in the code - and nobody knows if that was on purpose. "
                 "The next block came about six days later.\n\nMessage or accident? 👇" + NFA),
    hashtags='#Shorts #bitcoin #satoshi #crypto #cryptohistory', pinned='Message or accident? What do you think Satoshi meant? 👇',
    respell={},
    scenes=[
        sc('hook', 'shock', "Bitcoin's first block hides a newspaper headline.", 'headline', {'type': 'slam', 'text': 'A HIDDEN HEADLINE', 'sub': "IN BITCOIN'S FIRST BLOCK"}, fact='BLOCK 0 · THE GENESIS BLOCK'),
        sc('hook', 'shock', 'And its fifty Bitcoin can never be spent.', 'never', {'type': 'stamp', 'word': 'UNSPENDABLE', 'label': '50 BTC', 'icon': 'lock', 'bad': True}, fact='LOCKED FOREVER'),
        sc('setup', 'calm', 'January third, two thousand nine. Satoshi Nakamoto mined block zero.', 'zero', {'type': 'date', 'month': 'JAN', 'day': '3', 'event': 'BLOCK 0 IS MINED'}, fact='JANUARY 3, 2009', slam=('satoshi', 'SATOSHI')),
        sc('setup', 'curious', 'Inside, he wrote a line from The Times.', 'times', {'type': 'title', 'text': 'THE TIMES', 'sub': 'LONDON · 03/JAN/2009', 'icon': 'question'}, fact='A REAL NEWSPAPER, THAT MORNING'),
        sc('twist', 'shock', 'Chancellor on brink of second bailout for banks.', 'bailout',
           {'type': 'doc', 'head': 'THE TIMES · 03/JAN/2009', 'title': 'CHANCELLOR ON BRINK OF SECOND BAILOUT FOR BANKS'}, fact='WRITTEN INSIDE BLOCK 0', slam=('bailout', 'BAILOUT')),
        sc('turn', 'serious', 'So the block was not made before that day.', 'before', {'type': 'stamp', 'word': 'PROOF', 'label': 'NOT MADE BEFORE JAN 3', 'icon': 'calendar', 'bad': False}, fact='A TIMESTAMP NOBODY CAN FAKE'),
        sc('turn', 'curious', 'Many see it as a message about the banks.', 'banks', {'type': 'title', 'text': 'A MESSAGE?', 'sub': 'MONEY WITHOUT BANKS', 'icon': 'bank'}, fact='2008 FINANCIAL CRISIS'),
        sc('turn', 'excited', 'The reward was fifty Bitcoin.', 'fifty', {'type': 'counter', 'value': 50, 'suffix': ' BTC', 'label': 'THE FIRST BLOCK REWARD', 'icon': 'bitcoin'}, fact='THE VERY FIRST BITCOIN'),
        sc('twist', 'shock', 'Plot twist: a quirk in the code makes it unspendable.', 'unspendable', {'type': 'stamp', 'word': 'LOCKED', 'label': 'A QUIRK IN THE CODE', 'icon': 'lock', 'bad': True}, fact='THOSE 50 BTC CAN NEVER MOVE', slam=('quirk', 'PLOT TWIST')),
        sc('turn', 'curious', 'Nobody knows if that was on purpose.', 'purpose', {'type': 'title', 'text': 'ON PURPOSE?', 'sub': 'NOBODY KNOWS', 'icon': 'question'}, fact='SATOSHI NEVER EXPLAINED'),
        sc('payoff', 'shock', 'And the next block came about six days later.', 'six', {'type': 'counter', 'value': 6, 'suffix': ' DAYS', 'label': 'UNTIL BLOCK 1', 'icon': 'calendar'}, fact='BLOCKS NORMALLY COME EVERY 10 MINUTES', slam=('next', 'SIX DAYS?!')),
        END('Message or accident?'),
    ])

S['split'] = dict(jid='t3700074', num=34, title='The Night Bitcoin Split in Two ⚡ #Shorts', tone='mystery', theme='crimson',
    description=("March 11, 2013: Bitcoin split into two chains.\n"
                 "The new version 0.8 accepted a huge block (block 225,430, over 5,000 transactions). Older versions couldn't read it - their "
                 "database ran out of locks. Mt. Gox and BitPay paused deposits and the price dropped 24%.\n"
                 "Developers chose the old chain, big mining pools downgraded, and about six hours later the chains joined again. "
                 "24 blocks were wiped out, and a $10,000 double spend hit OKPay.\n\nBug or warning? 👇" + NFA),
    hashtags='#Shorts #bitcoin #crypto #cryptohistory #blockchain', pinned='Would you have picked the old chain or the new one? 👇',
    respell={'OKPay': 'Oh-Kay Pay', '0.8': 'zero point eight', 'BitPay': 'Bit Pay', 'Mt.': 'Mount'},
    scenes=[
        sc('hook', 'shock', 'In 2013, Bitcoin split into two chains.', 'split', {'type': 'slam', 'text': 'BITCOIN SPLIT', 'sub': 'INTO TWO CHAINS'}, fact='MARCH 11, 2013'),
        sc('hook', 'shock', 'And developers chose to kill the newer one.', 'kill', {'type': 'versus', 'left': ['OLD CHAIN', '0.7'], 'right': ['NEW CHAIN', '0.8'], 'note': 'ONE HAD TO DIE'}, fact='THE NEWER CHAIN LOST'),
        sc('setup', 'calm', 'March eleventh, 2013. Bitcoin version zero point eight was brand new.', 'new', {'type': 'date', 'month': 'MAR', 'day': '11', 'event': 'BITCOIN 0.8 IS NEW'}, fact='A NEW DATABASE: LEVELDB'),
        sc('setup', 'serious', 'Then one huge block hit the network, with over five thousand transactions.', 'huge', {'type': 'counter', 'value': 5000, 'prefix': '>', 'label': 'TRANSACTIONS IN ONE BLOCK', 'icon': 'bitcoin'}, fact='BLOCK 225,430', slam=('block', 'ONE HUGE BLOCK')),
        sc('twist', 'shock', "New nodes accepted it. Old nodes couldn't read it.", 'read', {'type': 'versus', 'left': ['NEW 0.8', 'ACCEPTED'], 'right': ['OLD 0.7', 'REJECTED'], 'note': 'SAME BLOCK'}, fact='TWO VERSIONS, TWO ANSWERS'),
        sc('turn', 'serious', 'Their old database ran out of locks. Bitcoin split in two.', 'split', {'type': 'stamp', 'word': 'SPLIT', 'label': 'BERKELEY DB · OUT OF LOCKS', 'icon': 'lock', 'bad': True}, fact='MORE THAN 10,000 LOCKS NEEDED', slam=('split', 'CHAIN SPLIT')),
        sc('turn', 'serious', 'Mt. Gox and BitPay paused deposits.', 'paused', {'type': 'stamp', 'word': 'PAUSED', 'label': 'MT. GOX · BITPAY', 'icon': 'safe', 'bad': True}, fact='FEAR OF DOUBLE SPENDS'),
        sc('payoff', 'shock', 'The price dropped twenty-four percent.', 'percent', {'type': 'counter', 'value': 24, 'prefix': '-', 'suffix': '%', 'label': 'BITCOIN PRICE', 'icon': 'fire'}, fact='DURING THE SPLIT', slam=('dropped', 'PANIC')),
        sc('twist', 'excited', 'Developers picked the old chain. Big mining pools downgraded.', 'downgraded', {'type': 'title', 'text': 'GO BACK TO 0.7', 'sub': 'BTC GUILD · SLUSH', 'icon': 'robot'}, fact='THE FIX: GO BACKWARDS', slam=('old', 'GO BACK')),
        sc('turn', 'calm', 'About six hours later, the chains joined again.', 'joined', {'type': 'counter', 'value': 6, 'prefix': '~', 'suffix': ' HOURS', 'label': 'UNTIL ONE CHAIN AGAIN', 'icon': 'calendar'}, fact='MARCH 12 · 06:19 GMT',
           receipt={'src': 'Bitcoin Magazine', 'headline': 'Bitcoin Network Shaken by Blockchain Fork', 'kind': 'headline'}),
        sc('payoff', 'shock', 'Twenty-four blocks were wiped out.', 'wiped', {'type': 'counter', 'value': 24, 'suffix': ' BLOCKS', 'label': 'ERASED', 'icon': 'skull'}, fact='ABOUT $26,000 IN LOST REWARDS', slam=('wiped', 'ERASED')),
        sc('payoff', 'shock', 'And someone double spent ten thousand dollars against OKPay.', 'double', {'type': 'counter', 'value': 10000, 'prefix': '$', 'label': 'DOUBLE SPENT', 'icon': 'cash'}, fact='PAID TWICE WITH THE SAME COINS'),
        END('Bug or warning?'),
    ])

S['satoshi'] = dict(jid='t3700075', num=35, title='Satoshi’s Last Email… Then He Vanished 👻 #Shorts', tone='mystery', theme='crimson',
    description=("Satoshi Nakamoto's last public forum post was in December 2010.\n"
                 "On April 23, 2011 he emailed developer Mike Hearn: \"I've moved on to other things. It's in good hands with Gavin and everyone.\"\n"
                 "Around the same time he wrote to Gavin Andresen: \"I wish you wouldn't keep talking about me as a mysterious shadowy figure, "
                 "the press just turns that into a pirate currency angle.\"\n"
                 "On April 27, 2011 Gavin announced he would talk about Bitcoin at the CIA. Gavin later said: \"The last email I sent him, "
                 "I actually told him I was going to talk at the CIA.\"\nSatoshi is believed to hold about a million Bitcoin that have never moved.\n\n"
                 "Coincidence? 👇" + NFA),
    hashtags='#Shorts #bitcoin #satoshi #crypto #cryptohistory', pinned='Why do YOU think Satoshi disappeared? 👇',
    respell={'CIA': 'C I A'},
    scenes=[
        sc('hook', 'shock', "Bitcoin's creator sent one last email. Then he went silent.", 'silent', {'type': 'slam', 'text': 'THE LAST EMAIL', 'sub': 'THEN SATOSHI VANISHED'}, fact='APRIL 2011'),
        sc('hook', 'curious', 'And days later, the CIA came into the story.', 'cia', {'type': 'title', 'text': 'THE CIA?', 'icon': 'question'}, fact='CENTRAL INTELLIGENCE AGENCY'),
        sc('setup', 'calm', 'December 2010. Satoshi made his last public forum post.', 'last', {'type': 'date', 'month': 'DEC', 'day': '12', 'event': 'LAST FORUM POST'}, fact='DECEMBER 12, 2010'),
        sc('setup', 'serious', 'April 23rd, 2011. He emailed developer Mike Hearn.', 'emailed', {'type': 'date', 'month': 'APR', 'day': '23', 'event': 'EMAIL TO MIKE HEARN'}, fact='APRIL 23, 2011', slam=('emailed', 'ONE EMAIL')),
        sc('twist', 'shock', "I've moved on to other things.", 'moved',
           {'type': 'quote', 'name': 'Satoshi Nakamoto', 'text': "I've moved on to other things."}, fact='EMAIL TO MIKE HEARN', slam=('moved', 'GOODBYE')),
        sc('turn', 'calm', "It's in good hands with Gavin and everyone.", 'gavin',
           {'type': 'quote', 'name': 'Satoshi Nakamoto', 'text': "It's in good hands with Gavin and everyone."}, fact='GAVIN ANDRESEN = LEAD DEVELOPER'),
        sc('turn', 'curious', 'Around the same days, he wrote to Gavin Andresen.', 'andresen', {'type': 'person', 'name': 'GAVIN ANDRESEN', 'role': 'LEAD DEVELOPER', 'prop': 'laptop'}, fact='APRIL 2011'),
        sc('turn', 'serious', "I wish you wouldn't keep talking about me as a mysterious shadowy figure.", 'shadowy',
           {'type': 'quote', 'name': 'Satoshi Nakamoto', 'text': "I wish you wouldn't keep talking about me as a mysterious shadowy figure…"}, fact='EMAIL TO GAVIN', slam=('shadowy', 'SHADOWY FIGURE')),
        sc('turn', 'serious', 'The press just turns that into a pirate currency angle.', 'pirate',
           {'type': 'quote', 'name': 'Satoshi Nakamoto', 'text': '…the press just turns that into a pirate currency angle.'}, fact='EMAIL TO GAVIN'),
        sc('twist', 'shock', 'On April 27th, Gavin announced a talk at the CIA.', 'cia', {'type': 'date', 'month': 'APR', 'day': '27', 'event': 'TALK AT THE CIA'}, fact='APRIL 27, 2011', slam=('announced', 'THE CIA')),
        sc('payoff', 'shock', 'Gavin later said his last email told Satoshi about that talk.', 'last',
           {'type': 'quote', 'name': 'Gavin Andresen', 'text': 'The last email I sent him, I actually told him I was going to talk at the CIA.'}, fact='SATOSHI NEVER WROTE BACK PUBLICLY', slam=('told', 'NO REPLY')),
        sc('payoff', 'excited', 'Satoshi is believed to hold about a million Bitcoin. Untouched.', 'untouched', {'type': 'counter', 'value': 1000000, 'prefix': '~', 'suffix': ' BTC', 'label': 'NEVER MOVED', 'icon': 'bitcoin'}, fact='MINED IN BITCOIN\'S FIRST YEAR'),
        sc('end', 'curious', 'Coincidence?', 'coincidence', {'type': 'title', 'text': 'COINCIDENCE?', 'sub': 'YOU DECIDE', 'icon': 'question'}),
    ])

if __name__ == '__main__':
    key = sys.argv[1]
    st = S[key]; JID = st.pop('jid'); st.pop('num')
    sb = dict(st, chart={}, lesson='')
    sb.update({'length': 55, 'settings': {'length': 55, 'style': 'graphics', 'autorender': True, 'chart': 'off', 'energy': 'high', 'cuts': 'fast',
                                           'pace': 'fast', 'motion': 'strong', 'captions': 'key', 'music': 'off', 'whoosh': 'off'}})
    for k, s in enumerate(sb['scenes']):
        assert s['hit'].lower() in re.sub(r'[^\w\s]', ' ', s['line'].lower()).split(), (k, s['hit'])
    print('standard', qc.standard(sb))
    chk, probs = story.check(json.loads(json.dumps(sb)), strict=False)
    print('words', chk.get('words'), 'est', chk.get('est_secs'), probs)
    print('facts kept', sum(1 for s in chk['scenes'] if s.get('fact')))
    vj, _ = story.voice_job(chk)
    print('voice', [x[1] for x in vj['scenes']]); [print(' ', x[0]) for x in vj['scenes']]
    os.makedirs(f'jobs/{JID}', exist_ok=True)
    json.dump(sb, open(f'jobs/{JID}/storyboard.json', 'w'), indent=1, ensure_ascii=False)
    for f in ('autorender.flag', 'hold.flag'): open(f'jobs/{JID}/{f}', 'w').write('1')
    json.dump({'state': 'draft'}, open(f'jobs/{JID}/status.json', 'w'))
