"""Story 1/6 (Nov 15 2026): the Poly Network hacker who gave $610M back. Facts only.
Sources: CNBC Aug 23 2021 (more than $600M stolen; $610M regained excl. $33M frozen USDT; >$200M needed both parties' passwords;
'Mr. White Hat' shared the final private key; $500,000 bounty; chief security advisor offer; 'my efforts to contribute to the security
of the Poly project'); TechSpot / Computing / PC Gamer headlines (Aug 2021). Hack date Aug 10 2021."""
import os, sys, json, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'studio')); os.chdir(ROOT)
import story, qc

SLAM = {2: [('crypto', 'CRYPTO BRIDGE')], 9: [('offered', 'A REWARD?!')], 12: [('handed', 'GAME OVER')], 3: [('wallets', 'HIS WALLETS')], 4: [('time', 'A RECORD')], 6: [('started', 'PLOT TWIST')],
        7: [('transaction', 'A HIDDEN MESSAGE')], 10: [('job', 'A JOB?!')], 11: [('key', 'TWO KEYS')]}   # v2 (Nov 15): word slams
_n = [0]

def sc(role, emo, line, hit, visual, receipt=None):
    k = _n[0]; _n[0] += 1
    bt = [{'word': w, 'text': x} for w, x in SLAM.get(k, [])]
    for w, _ in SLAM.get(k, []): assert w in re.sub(r'[^\w\s]', ' ', line.lower()).split(), (k, w)
    d = {'role': role, 'emotion': emo, 'line': line, 'hit': hit, 'visual': visual, 'beats': bt, 'shots': [], 'footage': '', 'photo': ''}
    if receipt: d['receipt'] = receipt
    return d

JID = 't3700070'
SB = dict(
    title='A Hacker Stole $610 Million… Then Gave It All Back 🤯 #Shorts', tone='mystery', theme='crimson', chart={}, lesson='',
    description=("August 2021: a hacker exploited a bug in Poly Network's code and moved more than $610 million in crypto to his own wallets - "
                 "the biggest DeFi hack at the time.\nTether froze $33 million. Then the hacker started sending the money back, saying it was "
                 "his \"efforts to contribute to the security of the Poly project.\"\nPoly Network nicknamed him \"Mr. White Hat\", offered a $500,000 "
                 "bounty - and a job as Chief Security Advisor.\nOn August 23, 2021, he handed over the last private key.\n\nHero or thief? 👇\n\n"
                 "Not financial advice. Entertainment and education only."),
    hashtags='#Shorts #crypto #hacker #defi #cryptohistory #bitcoin',
    pinned='Hero or thief? What would YOU have done with $610 million? 👇',
    respell={'DeFi': 'Dee-fye', 'Tether': 'Tether'},
    scenes=[
        sc('hook', 'shock', 'A hacker stole six hundred million dollars. Then he gave it back.', 'stole',
           {'type': 'slam', 'text': '$610M STOLEN', 'sub': 'THEN HE GAVE IT BACK'}),
        sc('hook', 'shock', 'And the company offered him a job.', 'job',
           {'type': 'title', 'text': 'A JOB OFFER?!', 'icon': 'question'}),
        sc('setup', 'calm', 'August 2021. Poly Network moved crypto between blockchains.', 'blockchains',
           {'type': 'title', 'text': 'POLY NETWORK', 'sub': 'CROSS-CHAIN BRIDGE · AUG 2021'}),
        sc('setup', 'serious', 'One bug in its code let a hacker move the money to his wallets.', 'bug',
           {'type': 'stamp', 'word': 'EXPLOITED', 'label': 'ONE BUG IN THE CODE', 'icon': 'lock', 'bad': True}),
        sc('turn', 'shock', 'Over 610 million dollars. The biggest DeFi hack at the time.', 'biggest',
           {'type': 'counter', 'value': 610000000, 'prefix': '$', 'suffix': '', 'label': 'BIGGEST DEFI HACK AT THE TIME'}),
        sc('turn', 'serious', 'Tether froze 33 million of it.', 'froze',
           {'type': 'counter', 'value': 33000000, 'prefix': '$', 'suffix': '', 'label': 'FROZEN BY TETHER', 'icon': 'lock'}),
        sc('twist', 'shock', 'Then the hacker started sending it back.', 'back',
           {'type': 'title', 'text': 'HE SENT IT BACK', 'icon': 'cash'},
           {'src': 'Computing', 'headline': 'Poly Network hacker returns all the stolen crypto cash', 'kind': 'headline'}),
        sc('turn', 'curious', 'Inside a transaction, he called it his effort to help their security.', 'security',
           {'type': 'quote', 'name': 'The hacker', 'handle': 'message inside a transaction',
            'text': '…my efforts to contribute to the security of the Poly project.'}),
        sc('turn', 'excited', 'Poly Network nicknamed him Mr. White Hat.', 'white',
           {'type': 'title', 'text': '"MR. WHITE HAT"', 'sub': "POLY NETWORK'S NAME FOR HIM"}),
        sc('payoff', 'excited', 'They offered him a 500,000 dollar bounty.', 'bounty',
           {'type': 'counter', 'value': 500000, 'prefix': '$', 'suffix': '', 'label': 'BUG BOUNTY OFFERED', 'icon': 'cash'}),
        sc('payoff', 'shock', 'And a job: Chief Security Advisor.', 'advisor',
           {'type': 'person', 'name': 'MR. WHITE HAT', 'role': 'CHIEF SECURITY ADVISOR?', 'prop': 'laptop'},
           {'src': 'TechSpot', 'headline': 'Hacker returns $600M to Poly Network, is offered position as Chief Security Advisor', 'kind': 'headline'}),
        sc('turn', 'serious', 'Over 200 million stayed locked. It needed his key and theirs.', 'locked',
           {'type': 'stamp', 'word': 'LOCKED', 'label': '$200M+ · TWO KEYS NEEDED', 'icon': 'lock', 'bad': False}),
        sc('payoff', 'excited', 'On August 23rd, he handed over the final key.', 'final',
           {'type': 'stamp', 'word': 'KEY RETURNED', 'label': 'AUGUST 23, 2021', 'icon': 'safe', 'bad': False}),
        sc('end', 'curious', 'Hero or thief?', 'thief',
           {'type': 'versus', 'left': ['HERO', '?'], 'right': ['THIEF', '?'], 'note': 'YOU DECIDE'}),
    ])

if __name__ == '__main__':
    sb = dict(SB)
    sb.update({'length': 55, 'settings': {'length': 55, 'style': 'graphics', 'autorender': True, 'chart': 'off', 'energy': 'high', 'cuts': 'fast',
                                           'pace': 'fast', 'motion': 'strong', 'captions': 'key', 'music': 'off', 'whoosh': 'off'}})
    for k, s in enumerate(sb['scenes']):
        assert s['hit'].lower() in re.sub(r'[^\w\s]', ' ', s['line'].lower()).split(), (k, s['hit'])
    print('standard', qc.standard(sb))
    chk, probs = story.check(json.loads(json.dumps(sb)), strict=False)
    print('words', chk.get('words'), 'est', chk.get('est_secs'), probs)
    vj, _ = story.voice_job(chk)
    print('voice', [x[1] for x in vj['scenes']]); [print(' ', x[0]) for x in vj['scenes']]
    os.makedirs(f'jobs/{JID}', exist_ok=True)
    json.dump(sb, open(f'jobs/{JID}/storyboard.json', 'w'), indent=1, ensure_ascii=False)
    for f in ('autorender.flag', 'hold.flag'): open(f'jobs/{JID}/{f}', 'w').write('1')
    json.dump({'state': 'draft'}, open(f'jobs/{JID}/status.json', 'w'))
