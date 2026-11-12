"""Breaking: Jensen Huang resigns as Nvidia CEO (Nov 12 2026). Facts only, attributed.
Sources: Nvidia 8-K (SEC, Nov 12 2026); Yahoo Finance live (NYT second-affair report Nov 11, The Information report, memo quote,
'as much as 13%', ~$440B estimate); Al Jazeera live ('accused of spying for China', 33 years); CNBC Nov 11 (board met into evening);
Fortune Feb 2024 (founded 1993 at a Denny's); first $5T company Oct 29 2025."""
import os, sys, json, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'studio')); os.chdir(ROOT)
import story, qc

def sc(role, emo, line, hit, visual):
    return {'role': role, 'emotion': emo, 'line': line, 'hit': hit, 'visual': visual, 'beats': [], 'shots': [], 'footage': '', 'photo': ''}

JID = 't3700060'
SB = dict(
    title='Nvidia CEO Jensen Huang Just Resigned. Here’s What Happened 🚨', tone='serious', theme='crimson', chart={}, lesson='',
    description=("Nov 12, 2026: Jensen Huang resigned as Nvidia's CEO and left the board, effective immediately, after 33 years. Nvidia's filing gave no reason.\n"
                 "This week, reports said he had an affair with a woman now accused of spying for China, and The New York Times reported a second affair with an Nvidia executive.\n"
                 "In a memo to staff, Huang wrote: \"I was unfaithful to my wife... There is no excuse for what I did. I am deeply sorry.\"\n"
                 "Nvidia stock fell as much as 13%. CFO Colette Kress is interim CEO.\n\n"
                 "Allegations are as reported by the outlets named; nothing here is a finding of wrongdoing.\n\nNot financial advice."),
    hashtags='#nvidia #jensenhuang #stocks #ai #breakingnews #shorts',
    pinned='Can Nvidia stay on top without its founder? 👇',
    respell={'Kress': 'Kress', 'CFO': 'C F O', 'CEO': 'C E O'},
    scenes=[
        sc('hook', 'shock', 'The man who built Nvidia just quit. Effective immediately.', 'quit',
           {'type': 'slam', 'text': 'HUANG QUITS', 'sub': 'NVIDIA · NOV 12, 2026'}),
        sc('hook', 'serious', 'Jensen Huang resigned as CEO and left the board. No reason given.', 'reason',
           {'type': 'doc', 'head': 'FORM 8-K · NVIDIA CORP', 'title': 'CEO TRANSITION',
            'lines': ['Jensen Huang resigned as President,', 'Chief Executive Officer, and a member', 'of the Board, effective immediately.'],
            'stamp': 'NO REASON GIVEN'}),
        sc('setup', 'calm', "He co-founded Nvidia in 1993, at a Denny's.", 'denny',
           {'type': 'title', 'text': '1993', 'sub': "FOUNDED AT A DENNY'S"}),
        sc('setup', 'excited', 'Last year, it became the first company worth five trillion dollars.', 'trillion',
           {'type': 'counter', 'value': 5, 'prefix': '$', 'suffix': 'T', 'label': 'FIRST EVER · OCT 2025'}),
        sc('turn', 'serious', 'Reports said he had an affair. The woman is now accused of spying for China.', 'spying',
           {'type': 'stamp', 'word': 'ALLEGED', 'label': 'accused of spying for China', 'icon': 'question', 'bad': True}),
        sc('twist', 'shock', 'The Information linked her to firms that helped ship chips to China.', 'chips',
           {'type': 'title', 'text': 'CHIPS TO CHINA', 'sub': 'REPORTED BY THE INFORMATION'}),
        sc('turn', 'serious', 'Then The New York Times reported a second affair, with an Nvidia executive.', 'second',
           {'type': 'title', 'text': 'A SECOND AFFAIR', 'sub': 'REPORTED BY THE NEW YORK TIMES'}),
        sc('turn', 'serious', "Nvidia's board met into the evening to decide his fate.", 'fate',
           {'type': 'news', 'kicker': 'THE HEADLINES', 'items': [
               {'src': 'CNBC', 'headline': "Nvidia board meeting to decide CEO Jensen Huang's fate stretches into evening", 'word': 'board'},
               {'src': 'Yahoo Finance', 'headline': 'Nvidia reportedly preparing to oust CEO Huang', 'word': 'fate'}]}),
        sc('twist', 'shock', 'This morning, he was out.', 'out',
           {'type': 'slam', 'text': 'OUT', 'sub': 'AFTER 33 YEARS'}),
        sc('turn', 'serious', 'In a memo, he wrote: I was unfaithful to my wife. I am deeply sorry.', 'sorry',
           {'type': 'quote', 'name': 'Jensen Huang', 'handle': 'memo to Nvidia staff',
            'text': 'I was unfaithful to my wife. There is no excuse for what I did. I am deeply sorry.'}),
        sc('payoff', 'shock', 'Nvidia stock fell as much as thirteen percent.', 'thirteen',
           {'type': 'counter', 'value': 13, 'prefix': '−', 'suffix': '%', 'label': 'NVDA · NOV 12 · INTRADAY LOW'}),
        sc('payoff', 'shock', 'Yahoo Finance estimated about 440 billion dollars wiped out.', 'wiped',
           {'type': 'counter', 'value': 440, 'prefix': '$', 'suffix': 'B', 'label': 'VALUE WIPED OUT · ESTIMATE'}),
        sc('turn', 'calm', 'CFO Colette Kress is now interim CEO.', 'interim',
           {'type': 'person', 'name': 'COLETTE KRESS', 'role': 'INTERIM CEO', 'prop': 'laptop'}),
        sc('end', 'curious', 'Nvidia without its founder. Still on top?', 'top',
           {'type': 'title', 'text': 'STILL ON TOP?', 'sub': 'NVIDIA WITHOUT ITS FOUNDER', 'icon': 'question'}),
    ])

if __name__ == '__main__':
    sb = dict(SB)
    sb.update({'length': 60, 'settings': {'length': 60, 'style': 'graphics', 'autorender': True, 'chart': 'off', 'energy': 'dynamic',
                                           'pace': 'fast', 'motion': 'strong', 'captions': 'key', 'music': 'off', 'whoosh': 'off'}})
    for k, s in enumerate(sb['scenes']):
        assert s['hit'].lower() in re.sub(r'[^\w\s]', ' ', s['line'].lower()).split(), (k, s['hit'])
    print('standard', qc.standard(sb))
    chk, probs = story.check(json.loads(json.dumps(sb)), strict=False)
    print('words', chk.get('words'), 'est', chk.get('est_secs'), probs)
    vj, _ = story.voice_job(chk)
    print('voice cfg', vj['cfg'], [x[1] for x in vj['scenes']]); [print(' ', x[0]) for x in vj['scenes']]
    print([s['visual']['type'] for s in chk['scenes']])
    os.makedirs(f'jobs/{JID}', exist_ok=True)
    json.dump(sb, open(f'jobs/{JID}/storyboard.json', 'w'), indent=1, ensure_ascii=False)
    for f in ('autorender.flag', 'hold.flag'): open(f'jobs/{JID}/{f}', 'w').write('1')
    json.dump({'state': 'draft'}, open(f'jobs/{JID}/status.json', 'w'))
