"""Hand-written, fact-checked storyboards for the Nov 2 2026 batch (library st-34, st-21, st-22, st-23, st-33).
python tests/batch_nov2.py  -> jobs/<jid>/storyboard.json + autorender/hold flags"""
import os, sys, json, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'studio')); os.chdir(ROOT)
import story

SET = {'length': 60, 'style': 'graphics', 'autorender': True}
NFA = '\n\nNot financial advice. Entertainment and education only.'


def sc(role, emo, line, hit, visual, receipt=None):
    s = {'role': role, 'emotion': emo, 'line': line, 'hit': hit, 'visual': visual, 'beats': [], 'shots': [], 'footage': '', 'photo': ''}
    if receipt: s['receipt'] = receipt
    return s


def rc(src, headline, kind='headline'):
    return {'src': src, 'headline': headline, 'kind': kind}


JOBS = {}

JOBS['t3700034'] = dict(
    title="He Said 4–5 Weeks. It's Day 247 ⏳", tone='serious', theme='crimson', lib='st-34',
    chart={'symbol': 'BTC', 'start': '2026-02-27', 'end': '2026-11-02'},
    lesson='Markets move on words. Your money should move on facts.',
    description="Feb 28, 2026: US and Israeli strikes on Iran began. Mar 1, Trump: \"We intended four to five weeks.\" "
                "We counted every dated, on-record statement where he said the war would end soon, was nearly over, or that a deal to end it was days away: at least 30 (Mar 1 to Nov 1). "
                "Mar 9 \"very soon\": oil fell from above $110 to the mid-$80s, bitcoin rose to about $69K. Apr 7 ceasefire: bitcoin +2.6% in an hour. "
                "Jul 8 ceasefire \"over\": bitcoin about $62K. Trump says (Oct 1) his 4-6 weeks meant the Iran nuclear threat." + NFA,
    hashtags='#Iran #Trump #Bitcoin #Oil #Markets #ChainSecrets #shorts',
    pinned='Should markets react to "soon" anymore? 👇',
    respell={},
    scenes=[
        sc('hook', 'shock', "Four to five weeks. That's how long the Iran war was supposed to take. It's been 247 days.", 'days',
           {'type': 'counter', 'value': 247, 'prefix': '', 'suffix': '', 'label': 'DAYS OF WAR'}),
        sc('setup', 'tense', 'February 28, 2026. US and Israeli strikes hit Iran.', 'strikes',
           {'type': 'date', 'month': 'FEB', 'day': '28', 'event': 'STRIKES ON IRAN'}),
        sc('setup', 'curious', "The next day, Trump says: 'We intended four to five weeks.'", 'weeks',
           {'type': 'quote', 'name': 'Donald Trump · Mar 1, 2026', 'text': 'We intended four to five weeks.'}),
        sc('turn', 'shock', "March 9: 'Soon. Very soon.' Oil had spiked above 110 dollars. It falls back to the mid-80s.", 'falls',
           {'type': 'versus', 'left': ['OIL SPIKE', '$110+'], 'right': ["AFTER 'SOON'", 'MID-$80s'], 'note': 'ONE SENTENCE'},
           rc('CNN', 'Oil prices dive as Trump says Iran war will end ‘very soon’')),
        sc('turn', 'curious', 'Bitcoin jumps to 69,000.', 'jumps',
           {'type': 'chart', 'date': '2026-03-09', 'label': "'VERY SOON' · BTC ~$69K"}),
        sc('turn', 'triumph', 'April 7: a two-week ceasefire. Bitcoin jumps 2.6 percent in one hour.', 'hour',
           {'type': 'chart', 'date': '2026-04-07', 'label': 'CEASEFIRE · +2.6% IN 1 HOUR'}),
        sc('turn', 'tense', "June: a deal is 'two or three days' away.", 'away',
           {'type': 'quote', 'name': 'Donald Trump · Jun 9, 2026', 'text': '…upon signing, which could be in two or three days.'}),
        sc('twist', 'dark', "July 8: the ceasefire is 'over.' Bitcoin drops to 62,000.", 'drops',
           {'type': 'chart', 'date': '2026-07-08', 'label': "'CEASEFIRE OVER' · BTC ~$62K"}),
        sc('twist', 'tense', "September: the war 'will end immediately after our election.'", 'election',
           {'type': 'title', 'text': 'AFTER THE ELECTION', 'icon': 'calendar'},
           rc('Al Jazeera', 'Trump says Iran war ‘will end immediately’ after US midterm elections')),
        sc('twist', 'curious', "November 1: 'We'll put it away very soon.'", 'soon',
           {'type': 'quote', 'name': 'Donald Trump · Nov 1, 2026', 'text': "We'll put it away very soon, one way or the other."}),
        sc('payoff', 'shock', 'We counted every time on the record. At least 30 times, he said the end was near.', 'near',
           {'type': 'counter', 'value': 30, 'prefix': '', 'suffix': '+', 'label': "TIMES 'SOON' · ON RECORD"}),
        sc('payoff', 'calm', 'Every time, the market listened. Trump now says those weeks meant the nuclear threat.', 'threat',
           {'type': 'title', 'text': 'HIS ANSWER', 'sub': "the weeks = the nuclear threat", 'icon': 'question'},
           rc('Poynter', 'Trump said the Iran war would last weeks. Now he says the media got it wrong.')),
        sc('end', 'dark', 'Day 247. No final deal.', 'deal',
           {'type': 'chart', 'date': '2026-11-01', 'label': 'DAY 247 · NO FINAL DEAL'}),
    ])

JOBS['t3700021'] = dict(
    title='They Meant to Refund $100… They Sent $10.5 Million 💸', tone='funny', theme='emerald', lib='st-21', chart=None,
    lesson='Money sent to you by mistake is never yours. It always comes back for you.',
    description="May 2021: Crypto.com owed an Australian customer a refund of about A$100. An employee entered an account number in the amount field and A$10.47 million was sent. "
                "Nobody noticed for seven months, until a December 2021 audit. By then a A$1.35M house in Melbourne had been bought for her sister. "
                "The Supreme Court of Victoria ordered the house sold and the money returned, with interest." + NFA,
    hashtags='#CryptoCom #Crypto #Mistake #Australia #ChainSecrets #shorts',
    pinned='Be honest: would YOU have noticed $10 million in your account? 👇',
    respell={},
    scenes=[
        sc('hook', 'shock', '10.5 million Australian dollars. Sent by mistake. It was supposed to be a 100 dollar refund.', 'mistake',
           {'type': 'counter', 'value': 10470000, 'prefix': 'A$', 'suffix': '', 'label': 'SENT BY MISTAKE'}),
        sc('setup', 'curious', 'May 2021. Crypto.com, the company that paid 700 million dollars to put its name on an arena in Los Angeles, owes an Australian woman a small refund. About 100 dollars.', 'refund',
           {'type': 'title', 'text': 'REFUND: A$100', 'sub': 'May 2021', 'icon': 'cash'}),
        sc('turn', 'funny', 'An employee types her account number… into the amount box.', 'box',
           {'type': 'versus', 'left': ['AMOUNT BOX', 'A$100'], 'right': ['TYPED IN', 'ACCOUNT NO.'], 'note': 'ONE WRONG BOX'}),
        sc('turn', 'shock', '10.47 million dollars lands in her account. And nobody notices.', 'notices',
           {'type': 'counter', 'value': 10470000, 'prefix': 'A$', 'suffix': '', 'label': 'LANDS IN HER ACCOUNT'},
           rc('Yahoo Finance', 'Woman buys house after crypto firm accidentally sends her $10.5 million')),
        sc('turn', 'funny', 'Not for a day. Not for a week. For seven months.', 'months',
           {'type': 'timer', 'text': '7 MONTHS', 'label': 'NOBODY NOTICED'}),
        sc('twist', 'tense', 'In December, an audit finally finds the hole.', 'hole',
           {'type': 'stamp', 'icon': 'safe', 'label': 'DECEMBER 2021 AUDIT', 'word': 'FOUND IT', 'bad': True}),
        sc('twist', 'funny', 'But the money has already moved. A five-bedroom house in Melbourne. 1.35 million dollars. Bought for her sister.', 'sister',
           {'type': 'title', 'text': 'A$1.35M HOUSE', 'sub': 'bought for her sister', 'icon': 'house'},
           rc('Decrypt', 'Crypto.com Sues Woman After Sending Her $10 Million by Mistake: Report')),
        sc('payoff', 'triumph', 'Crypto.com takes her to court. The judge orders the house sold.', 'sold',
           {'type': 'stamp', 'icon': 'gavel', 'label': 'SUPREME COURT OF VICTORIA', 'word': 'SELL IT', 'bad': True}),
        sc('end', 'funny', 'And the money goes back. With interest. One wrong box. Ten million dollars.', 'interest',
           {'type': 'face', 'mood': 'cry', 'text': 'WITH INTEREST', 'sub': 'one wrong box'}),
    ])

JOBS['t3700022'] = dict(
    title='They Mined Bitcoin on a Nuclear Weapons Supercomputer ☢️', tone='funny', theme='amber', lib='st-22',
    chart={'symbol': 'BTC', 'start': '2017-11-01', 'end': '2018-02-28'},
    lesson='Side money on a work computer is never secret. Someone is always watching.',
    description="Sarov, Russia: a closed city home to Russia's Federal Nuclear Center, where the first Soviet atomic bomb was built. "
                "In February 2018, engineers used the lab's one-petaflop supercomputer to mine crypto and were caught when they connected it to the internet. "
                "The institute called it \"a hopeless and criminal offense.\" In 2019 one engineer was fined 450,000 rubles (about $7,000)." + NFA,
    hashtags='#Bitcoin #Mining #Russia #Supercomputer #ChainSecrets #shorts',
    pinned='Worst place ever to mine bitcoin? 😂 👇',
    respell={'Sarov': 'Sah-rov', 'FSB': 'F S B'},
    scenes=[
        sc('hook', 'shock', 'They used a nuclear weapons supercomputer… to mine bitcoin.', 'bitcoin',
           {'type': 'title', 'text': 'NUCLEAR MINERS', 'icon': 'laptop'}),
        sc('setup', 'curious', "Sarov, Russia. A closed city that doesn't appear on maps.", 'maps',
           {'type': 'stamp', 'icon': 'question', 'label': 'SAROV, RUSSIA', 'word': 'NOT ON MAPS', 'bad': True}),
        sc('setup', 'tense', 'This is where the Soviet Union built its first atomic bomb. Today, it still works on nuclear warheads.', 'warheads',
           {'type': 'title', 'text': 'FIRST SOVIET A-BOMB', 'sub': 'built here', 'icon': 'fire'}),
        sc('setup', 'shock', 'Inside: a supercomputer with one petaflop of power. A million billion calculations every second.', 'second',
           {'type': 'title', 'text': '1 PETAFLOP', 'sub': 'a million billion calculations / second', 'icon': 'laptop'}),
        sc('turn', 'curious', 'February 2018. Bitcoin had touched almost 20,000 dollars two months earlier.', 'earlier',
           {'type': 'chart', 'date': '2017-12-17', 'label': 'DEC 2017 · ALMOST $20,000'}),
        sc('turn', 'funny', 'And a few engineers get an idea. They quietly put the supercomputer to work mining bitcoin.', 'mining',
           {'type': 'face', 'mood': 'wink', 'text': 'SIDE HUSTLE', 'sub': 'on a nuclear computer'}),
        sc('twist', 'tense', 'One problem. Mining needs the internet. And a nuclear weapons lab is supposed to stay offline.', 'offline',
           {'type': 'versus', 'left': ['MINING NEEDS', 'INTERNET'], 'right': ['NUKE LAB', 'OFFLINE'], 'note': 'UH-OH'}),
        sc('twist', 'shock', "The moment they connect it… security sees everything. Russia's security service, the FSB, walks in.", 'walks',
           {'type': 'stamp', 'icon': 'officer', 'label': "RUSSIA'S FSB", 'word': 'BUSTED', 'bad': True},
           rc('Fortune', 'Russia Arrests Nuclear Scientists Who Used a Supercomputer to Mine Bitcoin')),
        sc('twist', 'funny', "The lab calls it 'a hopeless and criminal offense.'", 'offense',
           {'type': 'quote', 'name': 'Institute press service', 'text': 'a hopeless and criminal offense'}),
        sc('payoff', 'funny', 'The price? One engineer was fined 450,000 rubles. About 7,000 dollars.', 'dollars',
           {'type': 'counter', 'value': 450000, 'prefix': '', 'suffix': ' RUB', 'label': 'THE FINE · ABOUT $7,000'},
           rc('Decrypt', 'Man fined $7,000 for using Russian supercomputer to mine Bitcoin')),
        sc('end', 'funny', 'The most powerful computer in town… and all it earned them was a fine.', 'fine',
           {'type': 'chart', 'date': '2018-02-09', 'label': 'FEB 2018 · BUSTED'}),
    ])

JOBS['t3700023'] = dict(
    title='He Borrowed $1 Billion… and Voted Himself the Treasury 🗳️', tone='mystery', theme='ocean', lib='st-23', chart=None,
    lesson='If votes can be borrowed, the vote can be bought.',
    description="April 2022: Beanstalk let token holders vote on proposals. An attacker submitted a proposal partly disguised as a donation to Ukraine, waited the one-day delay, "
                "then in a single transaction took about $1 billion in flash loans (Aave and others), bought voting power, passed his own proposal and drained about $181M. "
                "He repaid the loan in the same transaction, kept about $76M, and sent $250,000 to Ukraine." + NFA,
    hashtags='#DeFi #Ethereum #Hack #FlashLoan #ChainSecrets #shorts',
    pinned='Genius or villain? 🤔 👇',
    respell={'Aave': 'Ah-vay'},
    scenes=[
        sc('hook', 'shock', 'He borrowed one billion dollars… to vote himself the money.', 'money',
           {'type': 'counter', 'value': 1000000000, 'prefix': '$', 'suffix': '', 'label': 'BORROWED FOR ONE VOTE'}),
        sc('setup', 'curious', 'April 2022. Beanstalk, a crypto stablecoin project. Its rule: whoever holds the most votes decides.', 'decides',
           {'type': 'title', 'text': 'BEANSTALK', 'sub': 'most votes decides', 'icon': 'bank'}),
        sc('setup', 'curious', 'An attacker posts a proposal. It looks like a donation to Ukraine.', 'Ukraine',
           {'type': 'stamp', 'icon': 'question', 'label': 'PROPOSAL #18', 'word': 'A DONATION?', 'bad': False}),
        sc('turn', 'tense', 'Then he waits one day.', 'day',
           {'type': 'timer', 'text': '24 HRS', 'label': 'THE WAIT'}),
        sc('turn', 'shock', 'In one single transaction, he borrows about one billion dollars. A flash loan, from Aave and others.', 'loan',
           {'type': 'title', 'text': 'FLASH LOAN', 'sub': '~$1 billion · Aave + others', 'icon': 'bank'},
           rc('rekt.news', 'Beanstalk - REKT')),
        sc('turn', 'curious', 'A flash loan is money you borrow and repay in the same transaction. No credit check. No collateral.', 'collateral',
           {'type': 'list', 'items': ['BORROW $1B', 'USE IT', 'PAY IT BACK · SAME TX']}),
        sc('twist', 'dark', "He uses it to buy voting power. Votes yes on his own proposal. But hidden inside is code that sends him the project's money.", 'money',
           {'type': 'flow', 'from': 'BEANSTALK', 'to': ['ATTACKER'], 'amount': '$181M'}),
        sc('twist', 'shock', '181 million dollars, drained.', 'drained',
           {'type': 'counter', 'value': 181000000, 'prefix': '$', 'suffix': '', 'label': 'DRAINED'},
           rc('BleepingComputer', 'Beanstalk DeFi platform loses $182 million in flash-loan attack')),
        sc('payoff', 'dark', 'He pays the loan back in the same transaction. He walks away with about 76 million.', 'million',
           {'type': 'versus', 'left': ['PROTOCOL LOST', '$181M'], 'right': ['HE KEPT', '~$76M'], 'note': 'ONE TRANSACTION'}),
        sc('end', 'funny', 'And the Ukraine part? He really did send 250,000 dollars.', 'dollars',
           {'type': 'stamp', 'icon': 'cash', 'label': '$250,000 TO UKRAINE', 'word': 'REAL', 'bad': False}),
    ])

JOBS['t3700033'] = dict(
    title='61,000 Bitcoin Found in Britain… Taken from 128,000 People 👑', tone='serious', theme='teal', lib='st-33',
    chart={'symbol': 'BTC', 'start': '2017-01-01', 'end': '2026-11-02'},
    lesson='Every bitcoin move stays on a public record. Crime leaves a trail forever.',
    description="2014-2017: Zhimin Qian ran an investment fraud in China with 128,000 victims, then fled on a fake passport to the UK. "
                "UK police seized 61,000 BTC, a UK record. She wanted to become 'monarch' of the micronation Liberland. "
                "A transfer to her helper led police to arrest her in York in 2024. She pleaded guilty and in November 2025 was sentenced to 11 years and 8 months." + NFA,
    hashtags='#Bitcoin #Crime #UK #CryptoNews #ChainSecrets #shorts',
    pinned='What should happen to the 61,000 bitcoin? 👇',
    respell={'Zhimin Qian': 'Jee-min Chyen', 'Qian': 'Chyen'},
    scenes=[
        sc('hook', 'shock', '61,000 bitcoin. Found in Britain. Taken from 128,000 people in China.', 'Britain',
           {'type': 'counter', 'value': 61000, 'prefix': '', 'suffix': ' BTC', 'label': 'SEIZED IN THE UK'}),
        sc('setup', 'dark', '2014 to 2017. Zhimin Qian runs a fake investment scheme in China.', 'scheme',
           {'type': 'counter', 'value': 128000, 'prefix': '', 'suffix': '', 'label': 'VICTIMS IN CHINA'},
           rc('Al Jazeera', 'UK sentences Chinese scammer after record-breaking Bitcoin seizure')),
        sc('turn', 'tense', 'Police close in. She flees on a fake passport, through Southeast Asia, to the UK.', 'passport',
           {'type': 'stamp', 'icon': 'plane', 'label': 'FAKE PASSPORT', 'word': 'ESCAPED', 'bad': True}),
        sc('turn', 'curious', 'There, she lives a lavish life. And tries to buy London houses with bitcoin.', 'houses',
           {'type': 'title', 'text': 'LONDON HOUSES', 'sub': 'paid in bitcoin?', 'icon': 'house'}),
        sc('twist', 'shock', "That's her mistake. In 2018, a law firm raises the alarm. Police seize the bitcoin. 61,000 coins. A UK record.", 'record',
           {'type': 'chart', 'date': '2018-06-01', 'label': '2018 · 61,000 BTC SEIZED'}),
        sc('twist', 'funny', "Her dream: to become the 'monarch' of a tiny micronation called Liberland.", 'Liberland',
           {'type': 'title', 'text': 'QUEEN OF LIBERLAND?', 'icon': 'crown'}),
        sc('twist', 'tense', 'In 2024, a fast-food worker who helped her gets a small bitcoin transfer. Police are watching. They arrest her in York.', 'York',
           {'type': 'stamp', 'icon': 'officer', 'label': 'YORK, 2024', 'word': 'ARRESTED', 'bad': True}),
        sc('payoff', 'dark', 'In 2025, she pleads guilty. Her sentence: 11 years and 8 months. Her accomplice gets almost 5 years.', 'months',
           {'type': 'timer', 'text': '11Y 8M', 'label': 'HER SENTENCE'},
           rc('RNZ', 'UK court jails Chinese bitcoin fraudster for over 11 years')),
        sc('end', 'dark', 'Those coins? Worth almost 5 billion dollars today.', 'today',
           {'type': 'chart', 'date': '2026-11-02', 'label': 'TODAY · ~$4.75 BILLION'}),
    ])

if __name__ == '__main__':
    only = sys.argv[1:] or list(JOBS)
    for jid in only:
        j = dict(JOBS[jid])
        lib = j.pop('lib')
        sb = {'title': j['title'], 'tone': j['tone'], 'theme': j['theme'], 'length': 60, 'chart': j['chart'], 'lesson': j['lesson'],
              'description': j['description'], 'hashtags': j['hashtags'], 'pinned': j['pinned'], 'respell': j['respell'],
              'settings': dict(SET, chart='on' if j['chart'] else 'off'), 'scenes': j['scenes'], 'library': lib}
        for k, s in enumerate(sb['scenes']):
            assert s['hit'].lower() in re.sub(r'[^\w\s]', ' ', s['line'].lower()).split(), (jid, k, s['hit'])
        chk, probs = story.check(json.loads(json.dumps(sb)), strict=False)
        print(jid, 'words', chk.get('words'), 'est', chk.get('est_secs'), 'ok', chk.get('length_ok'), probs)
        os.makedirs(f'jobs/{jid}', exist_ok=True)
        json.dump(sb, open(f'jobs/{jid}/storyboard.json', 'w'), indent=1, ensure_ascii=False)
        for f in ('autorender.flag', 'hold.flag'): open(f'jobs/{jid}/{f}', 'w').write('1')
        json.dump({'state': 'draft'}, open(f'jobs/{jid}/status.json', 'w'))
