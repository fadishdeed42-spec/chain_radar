"""Trump-Iran long video: every spoken line + what the screen shows while it is spoken.
Voice text is respelled for Chatterbox (numbers as words). Visuals are keyed to the line (and to words inside it).
Approved script: https://claude.ai/artifact/3SfS1heNJfhUrmfhXwbbaU (Nov 3 2026)."""

# visual kinds: number, quote, chart, chapter, event, map, ships, bars, lesson, headline, compare, end
L = []
def line(c, t, ex=.6, g=.3, **v):
    L.append({'c': c, 't': t, 'ex': ex, 'g': g, 'v': v})

NUM = {'MAR 1': 1, 'MAR 9': 4, 'MAR 13': 8, 'MAR 17': 10, 'MAR 26': 13, 'MAR 31': 15, 'APR 1': 16, 'APR 7': 18, 'APR 16': 19, 'MAY 23': 21,
       'JUN 1': 22, 'JUN 9': 25, 'JUN 11': 26, 'AUG 6': 27, 'SEP 9': 28, 'SEP 12': 29, 'OCT 2': 30, 'OCT 9': 31, 'OCT 30': 32}
def quote(c, date, said, where, src, t, ex=.62, g=.32, counted=1, **kw):
    n = (33 if 'RSBN' in where else 34) if date == 'NOV 1' else NUM.get(date, 0)      # the statement's number in the approved count table
    line(c, t, ex, g, kind='quote', n=n if counted else 0, date=date, said=said, where=where, src=src, **kw)

# ---------------------------------------------------------------- 0. the number
line(0, 'Thirty-four.', .8, .55, kind='number', big='34', sub='TIMES')
line(0, "That's how many times, on the record, Donald Trump said the Iran war would end soon.", .62, .3,
     kind='number', big='34', sub='TIMES HE SAID THE WAR WOULD END SOON', hit='soon')
line(0, 'Or that it was almost over. Or that a deal to end it was days away.', .64, .4,
     kind='stack', items=['"END SOON"', '"ALMOST OVER"', '"A DEAL IS DAYS AWAY"'], hits=['soon.', 'over.', 'away.'])
line(0, 'We went through eight months of speeches, interviews and posts.', .58, .26,
     kind='files', items=['SPEECHES', 'INTERVIEWS', 'POSTS'], span='MAR 1 – NOV 1, 2026')
line(0, 'We counted every one we could prove, with the date and the source.', .6, .4,
     kind='files', items=['DATE', 'PLACE', 'SOURCE'], span='34 STATEMENTS · 34 SOURCES', stamp='VERIFIED')
line(0, 'Then we checked something else.', .62, .22, kind='duo', a='BITCOIN', b='OIL', reveal=0)
line(0, 'What bitcoin and oil actually did, on every one of those days.', .62, .4, kind='duo', a='BITCOIN', b='OIL', reveal=1)
line(0, 'The answer surprised us.', .78, .6, kind='number', big='?', sub='THE ANSWER SURPRISED US')

# ---------------------------------------------------------------- 1. montage (fast)
line(1, "Here's every kind of promise, in his own words.", .6, .3, kind='chapter', num='', title='IN HIS OWN WORDS', sub='The montage')
quote(1, 'MAR 1', 'We intended four to five weeks.', 'NYT interview', 'CBS News', 'March first. "We intended four to five weeks."', g=.24, fast=1)
quote(1, 'MAR 9', 'Soon. Very soon.', 'Miami press conference', 'CBS News', 'March ninth. "Soon. Very soon."', g=.24, fast=1)
quote(1, 'MAR 17', "We'll be leaving in pretty much the very near future.", 'Reporters', 'PBS', 'March seventeenth. "We\'ll be leaving in pretty much the very near future."', g=.24, fast=1)
quote(1, 'MAR 31', 'Two or three weeks.', 'Oval Office', 'CBS News', 'March thirty-first. "Two or three weeks."', g=.24, fast=1)
quote(1, 'APR 16', 'It should be ending pretty soon.', 'Nevada event', 'PBS', 'April sixteenth. "It should be ending pretty soon."', g=.24, fast=1)
quote(1, 'JUN 9', 'Two or three days.', 'After the NBA Finals', 'CBS News', 'June ninth. "Two or three days."', g=.24, fast=1)
quote(1, 'JUN 11', 'Over the next few days.', 'Oval Office', 'CBS News', 'June eleventh. "Over the next few days."', g=.24, fast=1)
quote(1, 'SEP 9', 'This war will end immediately after our election.', 'Joint Base Andrews', 'Al Jazeera', 'September ninth. "This war will end immediately after our election."', g=.24, fast=1)
quote(1, 'OCT 9', "One way or another, it's gonna be over soon.", 'White House event', 'Times of Israel', 'October ninth. "One way or another, it\'s gonna be over soon."', g=.24, fast=1)
quote(1, 'OCT 30', "It's going to get wrapped up soon.", 'KCMO radio', 'PTI / ThePrint', 'October thirtieth. "It\'s going to get wrapped up soon."', g=.24, fast=1)
quote(1, 'NOV 1', "We'll put it away very soon.", 'RSBN interview, Iowa', 'CBS News', 'November first. "We\'ll put it away very soon."', g=.2, fast=1)
quote(1, 'NOV 1', "It's going to be over very soon. Very soon.", 'Iowa rally', 'Fox News', 'And that same night: "It\'s going to be over very soon. Very soon."', g=.4, fast=1)
line(1, "Thirty-four times. Here's what happened in between.", .7, .6, kind='number', big='34', sub="HERE'S WHAT HAPPENED IN BETWEEN", hit='Thirty-four')

# ---------------------------------------------------------------- 2. four to five weeks
line(2, 'Chapter one. Four to five weeks.', .6, .4, kind='chapter', num='CHAPTER 1', title='FOUR TO FIVE WEEKS', sub='Feb 28 – Apr 8')
line(2, 'February twenty-eighth, twenty twenty-six. American and Israeli strikes hit Iran.', .66, .3,
     kind='event', date='FEB 28, 2026', head='US and Israeli strikes hit Iran', tag='DAY 1')
line(2, "Iran answers by closing the Strait of Hormuz, the narrow channel that about a fifth of the world's oil passes through.", .62, .34,
     kind='map', state='closed', label='STRAIT OF HORMUZ', sub='~1/5 of the world\'s oil passes here', hit='closing')
line(2, 'The day before the war, US oil closed at sixty-seven dollars a barrel.', .58, .22,
     kind='chart', series='wti', a='2026-02-02', b='2026-02-27', mark='2026-02-27', tag='$66.96', title='US OIL (WTI) · DAY BEFORE THE WAR')
line(2, 'Bitcoin closed near sixty-five thousand nine hundred.', .58, .32,
     kind='chart', series='btc', a='2026-02-02', b='2026-02-27', mark='2026-02-27', tag='$65,868', title='BITCOIN · DAY BEFORE THE WAR')
quote(2, 'MAR 1', 'We intended four to five weeks.', 'NYT interview', 'CBS News', 'The next day, Trump gives his first timeline. "We intended four to five weeks."', hit='intended')
line(2, "Oil doesn't wait. By March sixth, it's at ninety-one dollars.", .7, .32,
     kind='chart', series='wti', a='2026-02-02', b='2026-03-06', mark='2026-03-06', tag='$90.77', title='US OIL (WTI)', hit='ninety-one')
quote(2, 'MAR 9', 'Soon, very soon.', 'Miami press conference', 'CBS News', 'March ninth. Trump says the end is coming. "Soon, very soon."', hit='Soon,')
line(2, 'That day, bitcoin jumps almost four percent.', .68, .22,
     kind='chart', series='btc', a='2026-02-20', b='2026-03-09', mark='2026-03-09', tag='+3.8%', title='BITCOIN · MARCH 9', hit='jumps')
line(2, 'The next day, oil drops from ninety-five dollars to eighty-four.', .66, .26,
     kind='chart', series='wti', a='2026-02-20', b='2026-03-10', mark='2026-03-10', tag='$94.65 → $83.71', title='US OIL (WTI) · MARCH 10', hit='drops')
line(2, 'For a moment, the words work.', .62, .45, kind='number', big='FOR A MOMENT', sub='THE WORDS WORK', small=1)
line(2, 'But the war keeps going.', .6, .3, kind='event', date='MARCH 2026', head='The war keeps going', tag='')
quote(2, 'MAR 13', "I don't think it's gonna be long.", 'Fox News Radio', 'PBS', 'March thirteenth. "I don\'t think it\'s gonna be long."')
quote(2, 'MAR 26', "Four to six weeks. We're way ahead of schedule.", 'Cabinet meeting', 'PBS', 'March twenty-sixth. "Four to six weeks. We\'re way ahead of schedule."')
quote(2, 'MAR 31', 'Two or three weeks.', 'Oval Office', 'CBS News', 'March thirty-first. "Two or three weeks."')
line(2, 'By then, oil is above one hundred dollars.', .66, .34,
     kind='chart', series='wti', a='2026-02-20', b='2026-03-31', mark='2026-03-31', tag='$102.86', title='US OIL (WTI) · MARCH 31', hit='hundred')
quote(2, 'APR 1', 'Shortly, very shortly.', 'Address to the nation', 'PBS', 'April first, in an address to the nation, he promises to finish the job "shortly, very shortly."')
line(2, 'April seventh. Oil hits its highest price of the whole war. One hundred fourteen dollars.', .7, .3,
     kind='chart', series='wti', a='2026-02-20', b='2026-04-07', mark='2026-04-07', tag='$114.58  WAR HIGH', title='US OIL (WTI) · APRIL 7', hit='fourteen')
line(2, 'That night comes a two-week ceasefire.', .66, .26, kind='event', date='APR 7, 2026', head='A two-week ceasefire', tag='DAY 39')
line(2, 'Bitcoin jumps two point six percent in one hour, to seventy-two thousand three hundred.', .68, .24,
     kind='chart', series='btc', a='2026-03-10', b='2026-04-08', mark='2026-04-07', tag='+2.6% IN 1 HOUR · $72,339', title='BITCOIN · APRIL 7', hit='jumps')
line(2, 'The next day, oil falls sixteen percent.', .68, .3,
     kind='chart', series='wti', a='2026-03-10', b='2026-04-08', mark='2026-04-08', tag='−16%  $114.58 → $96.17', title='US OIL (WTI) · APRIL 8', hit='sixteen')
quote(2, 'APR 7', 'Total and complete victory. 100%.', 'AFP, after the ceasefire', 'PBS', 'Trump calls it "Total and complete victory. One hundred percent."', hit='victory.')
line(2, 'Five weeks had passed. The war had not ended.', .6, .7, kind='calendar', weeks=5, day=40, hit='ended.')

# ---------------------------------------------------------------- 3. days away
line(3, 'Chapter two. Days away.', .6, .4, kind='chapter', num='CHAPTER 2', title='DAYS AWAY', sub='Apr 8 – Jul 7')
line(3, 'The ceasefire mostly held.', .56, .24, kind='event', date='APRIL 2026', head='The ceasefire mostly holds', tag='')
line(3, 'But talks in Islamabad failed, and on April thirteenth, a US naval blockade of Iran\'s ports took effect.', .62, .3,
     kind='map', state='blockade', label='US NAVAL BLOCKADE', sub='In effect April 13', hit='blockade')
line(3, 'On April twenty-first, the ceasefire was extended, with no end date.', .56, .26,
     kind='event', date='APR 21, 2026', head='Ceasefire extended with no end date', tag='DAY 53')
line(3, 'In May, the US struck Iran twice more, and called it "self-defense."', .6, .36,
     kind='event', date='MAY 7 · MAY 25', head='Two more US strikes, called "self-defense"', tag='MAY')
line(3, 'And the deal was always almost done.', .64, .3, kind='number', big='ALMOST DONE', sub='THE DEAL, AGAIN AND AGAIN', small=1)
quote(3, 'MAY 23', 'Details will be announced shortly.', 'Truth Social', 'CBS News', 'May twenty-third. Details "will be announced shortly."')
quote(3, 'JUN 1', 'An agreement over the next week.', 'ABC News', 'CBS News', 'June first. An agreement, "over the next week."')
quote(3, 'JUN 9', 'Upon signing, which could be in two or three days.', 'After the NBA Finals', 'CBS News', 'June ninth. Signing "could be in two or three days."')
line(3, "Bitcoin didn't wait for it. From May thirty-first to June second, it fell more than nine percent.", .66, .26,
     kind='chart', series='btc', a='2026-05-01', b='2026-06-02', mark='2026-06-02', tag='−9.4% IN 2 DAYS', title='BITCOIN · JUNE 2', hit='nine')
line(3, 'By June thirtieth, it was at fifty-eight thousand five hundred.', .62, .34,
     kind='chart', series='btc', a='2026-05-01', b='2026-06-30', mark='2026-06-30', tag='$58,526', title='BITCOIN · JUNE 30', hit='fifty-eight')
line(3, 'June seventeenth. Finally, a signed paper. The Islamabad Memorandum, with sixty days to negotiate.', .64, .3,
     kind='doc', title='ISLAMABAD MEMORANDUM', sub='Signed June 17, 2026', lines=['60 days of negotiations', 'Nuclear program', 'The Strait of Hormuz', 'Frozen funds'], stamp='SIGNED', hit='signed')
line(3, 'The next day, the US ended the blockade, and Hormuz reopened.', .62, .26, kind='map', state='open', label='HORMUZ REOPENS', sub='June 18', hit='reopened.')
line(3, 'By early July, oil had slid below seventy dollars.', .6, .34,
     kind='chart', series='wti', a='2026-04-01', b='2026-07-06', mark='2026-07-06', tag='$69.60', title='US OIL (WTI) · JULY 6', hit='seventy')
line(3, 'For three weeks, it looked over.', .58, .7, kind='number', big='3 WEEKS', sub='IT LOOKED OVER', small=1)

# ---------------------------------------------------------------- 4. "I think it's over"
line(4, 'Chapter three. "I think it\'s over."', .6, .4, kind='chapter', num='CHAPTER 3', title='"I THINK IT\'S OVER"', sub='Jul 8 – Aug 31')
line(4, 'July eighth. Iran attacks three ships in Hormuz.', .7, .24, kind='map', state='attack', label='JULY 8', sub='Three ships attacked', hit='attacks')
line(4, 'The US strikes more than eighty targets.', .68, .22, kind='number', big='80+', sub='TARGETS STRUCK BY THE US', hit='eighty')
line(4, "Iran's Revolutionary Guards say they hit eighty-five US military sites in Bahrain and Kuwait.", .64, .3,
     kind='number', big='85', sub='US SITES IRAN SAYS IT HIT (BAHRAIN, KUWAIT)', hit='eighty-five')
quote(4, 'JUL 8', "I think it's over. I don't want to deal with them any more.", 'NATO summit, Ankara', 'Al Jazeera',
      'Trump, at the NATO summit. "I think it\'s over. I don\'t want to deal with them any more."', hit='over.', counted=0)
line(4, 'This time, "over" meant the ceasefire.', .6, .24, kind='headline', src='Al Jazeera', head='Trump says ceasefire over after US, Iran trade attacks', date='JUL 8, 2026')
line(4, 'Bitcoin fell about two and a half percent, to around sixty-two thousand.', .64, .34,
     kind='chart', series='btc', a='2026-06-01', b='2026-07-09', mark='2026-07-08', tag='≈ −2.5% · ≈ $62,000', title='BITCOIN · JULY 8', hit='fell')
line(4, 'July thirteenth. Trump says the blockade is coming back, with a toll on ships.', .64, .26,
     kind='headline', src='NPR', head='Trump says the U.S. will reinstate its blockade on Iran and charge a toll on ships', date='JUL 13, 2026')
line(4, 'In two trading days, Brent crude jumps eleven percent.', .68, .34, kind='number', big='+11%', sub='BRENT CRUDE IN TWO TRADING DAYS', hit='eleven')
quote(4, 'AUG 6', "I don't think they can go much longer.", 'Oval Office', 'The National Desk', 'August sixth, in the Oval Office. "I don\'t think they can go much longer."')
line(4, 'By late August, the war is six months old.', .58, .22, kind='calendar', weeks=26, day=180, months=6)
line(4, 'It has cost the US more than thirty-seven and a half billion dollars.', .64, .3, kind='number', big='$37.5B+', sub='COST TO THE US BY LATE AUGUST (AP)', hit='thirty-seven')
line(4, 'Before the war, about one hundred thirty ships a day crossed Hormuz. On August twenty-sixth, twenty-four did.', .62, .36,
     kind='ships', a=130, b=24, hit='twenty-four')
line(4, 'Then the tone changes.', .6, .22, kind='number', big='THE TONE CHANGES', sub='', small=1)
line(4, 'He\'s "not in a hurry" to get Iran back to the table.', .6, .22,
     kind='headline', src='AP', head="Trump used to say he saw a quick end to his Iran war, but 6 months later he claims he's in no hurry", date='AUG 28, 2026')
line(4, 'He posts. "Mission accomplished. Twenty twenty-six."', .66, .7, kind='post', text='MISSION ACCOMPLISHED 2026', where='Social media post, late August', hit='accomplished.')

# ---------------------------------------------------------------- 5. after the election
line(5, 'Chapter four. After the election.', .6, .4, kind='chapter', num='CHAPTER 4', title='AFTER THE ELECTION', sub='Sep 1 – Nov 1')
quote(5, 'SEP 9', 'This war will end immediately after our election.', 'Joint Base Andrews', 'Al Jazeera',
      'September ninth, at Joint Base Andrews. "This war will end immediately after our election."', hit='election.')
line(5, 'That week, US oil crossed one hundred dollars again.', .64, .34,
     kind='chart', series='wti', a='2026-07-01', b='2026-09-10', mark='2026-09-10', tag='$103.57', title='US OIL (WTI) · SEPTEMBER 10', hit='hundred')
quote(5, 'SEP 12', "I think it'll be right after the midterms, actually.", 'Ireland visit', 'The Post Millennial',
      'Three days later, in Ireland. "I think it\'ll be right after the midterms, actually."')
quote(5, 'SEP 12', 'And oil will come tumbling down when that happens.', 'Ireland visit', 'The Post Millennial',
      '"And oil will come tumbling down when that happens."', counted=0, hit='tumbling')
quote(5, 'OCT 2', "It's going to end very soon and probably right after the midterms.", 'Rally, Mobile, Alabama', 'Iran International',
      'October second, at a rally in Mobile, Alabama. "It\'s going to end very soon, and probably right after the midterms."')
line(5, 'October eighth, on Truth Social. The blockade stays.', .6, .2,
     kind='post', text='…the Blockade will remain in full force and effect…', where='Truth Social · Oct 8, 2026', hit='stays.')
line(5, 'But "we will not be attacking Iran at any time prior to the Midterm Elections."', .62, .34,
     kind='post', text='…we will not be attacking Iran at any time prior to the Midterm Elections…', where='Truth Social · Oct 8, 2026')
quote(5, 'OCT 9', "One way or another it's gonna be over soon.", 'White House event', 'Times of Israel', 'October ninth. "One way or another, it\'s gonna be over soon."')
quote(5, 'OCT 30', "It's going to get wrapped up soon.", 'KCMO radio', 'PTI / ThePrint', 'October thirtieth. "It\'s going to get wrapped up soon."')
quote(5, 'NOV 1', "We'll put it away very soon, one way or the other.", 'RSBN interview, before the Iowa rally', 'CBS News',
      'November first. Before a rally in Iowa. "We\'ll put it away very soon, one way or the other."')
quote(5, 'NOV 1', "It's going to be over very soon. Very soon.", 'Iowa rally', 'Fox News', 'On stage that night. "It\'s going to be over very soon. Very soon."')
quote(5, 'NOV 1', "At some point, we're going to have to give them the hammer.", 'Iowa rally', 'Fox News',
      'And. "At some point, we\'re going to have to give them the hammer."', counted=0, hit='hammer.')
line(5, 'By the end of October, the Pentagon counted twenty-three American service members killed in the war.', .5, .3,
     kind='number', big='23', sub='US SERVICE MEMBERS KILLED (PENTAGON, OCT 30)', hit='twenty-three', somber=1)
line(5, 'Oil was up about seventy percent from a year earlier.', .58, .6, kind='number', big='+70%', sub='OIL vs A YEAR EARLIER (OCT 30)', hit='seventy')

# ---------------------------------------------------------------- 6. did the market believe him
line(6, 'Chapter five. Did the market believe him?', .62, .4, kind='chapter', num='CHAPTER 5', title='DID THE MARKET BELIEVE HIM?', sub='The test')
line(6, "Here's the part we didn't expect.", .66, .22, kind='number', big='THE TEST', sub='', small=1)
line(6, 'We lined up all thirty-four statements against the daily prices.', .6, .34, kind='dots', series='btc', hit='thirty-four')
line(6, 'He said it on thirty-one different days.', .6, .22, kind='dots', series='btc', show='days', hit='thirty-one')
line(6, 'Bitcoin closed higher on sixteen of them, and lower on fifteen.', .64, .24, kind='bars', a=16, b=15, la='UP DAYS', lb='DOWN DAYS', title='BITCOIN ON THE 31 DAYS', hit='sixteen')
line(6, "That's a coin flip.", .74, .4, kind='coin', hit='flip.')
line(6, 'Oil? In the trading session on or after his statements, US oil went up nineteen times out of twenty-seven.', .62, .26,
     kind='bars', a=19, b=8, la='UP', lb='DOWN', title='US OIL (WTI) · 27 SESSIONS', hit='nineteen')
line(6, 'The words said "almost over."', .62, .2, kind='versus', a='THE WORDS', av='"ALMOST OVER"', b='THE OIL PRICE', bv='"NOT YET"', reveal=0)
line(6, 'The oil price kept saying "not yet."', .66, .4, kind='versus', a='THE WORDS', av='"ALMOST OVER"', b='THE OIL PRICE', bv='"NOT YET"', reveal=1)
line(6, "The biggest moves didn't come from words. They came from events.", .64, .24, kind='events', hit='events.')
line(6, 'The April seventh ceasefire. The June memorandum. The July eighth collapse. The blockade.', .62, .34, kind='events', step=1)
line(6, 'From the day before the first strike to November second, bitcoin rose about sixteen percent.', .6, .22,
     kind='chart', series='btc', a='2026-02-27', b='2026-11-02', mark='2026-11-02', tag='+16%', title='BITCOIN · THE WHOLE WAR', hit='sixteen', full=1)
line(6, 'By late October, US oil was up about fifty-four percent.', .64, .55,
     kind='chart', series='wti', a='2026-02-27', b='2026-10-27', mark='2026-10-27', tag='+54%', title='US OIL (WTI) · THE WHOLE WAR', hit='fifty-four', full=1)

# ---------------------------------------------------------------- 7. his side and the count
line(7, 'His side, and the count.', .58, .4, kind='chapter', num='FAIRNESS', title='HIS SIDE AND THE COUNT', sub='')
line(7, 'Trump has his own answer.', .56, .22, kind='number', big='HIS ANSWER', sub='', small=1)
line(7, 'On October first, he said his "four to six weeks" meant the Iran nuclear threat, which he says he ended "in one night."', .58, .36,
     kind='quote', n=0, date='OCT 1', said='Four to six weeks … meant the nuclear threat, ended "in one night."', where='His explanation', src='Poynter', paraphrase=1)
line(7, 'Other counts use other rules.', .56, .22, kind='counts', step=0)
line(7, 'Axios counted twelve signals by March thirtieth.', .56, .2, kind='counts', step=1, hit='twelve')
line(7, 'C N N counted thirty-eight times he said a deal was close, by June ninth.', .56, .22, kind='counts', step=2, hit='thirty-eight')
line(7, 'Our rule. One dated, public statement per place, per day.', .56, .22, kind='counts', step=3)
line(7, 'All thirty-four sources are in the description.', .56, .6, kind='counts', step=4)

# ---------------------------------------------------------------- 8. the lesson
line(8, "So what's the lesson for traders?", .62, .3, kind='chapter', num='THE LESSON', title='FOR TRADERS', sub='')
line(8, 'One. A promise isn\'t a price.', .7, .2, kind='lesson', step=1, hit='price.')
line(8, 'Bitcoin treated thirty-four "soons" like noise.', .62, .34, kind='lesson', step=1)
line(8, 'Two. Watch what you can measure.', .68, .2, kind='lesson', step=2)
line(8, 'Ships through Hormuz. The blockade. A signed paper. Those moved the market.', .62, .34, kind='lesson', step=2)
line(8, 'Three. When someone says "soon," ask: soon compared to what?', .66, .24, kind='lesson', step=3)
line(8, 'Four to five weeks has now lasted more than eight months.', .62, .45, kind='calendar', weeks=35, day=248, months=8, hit='eight')
line(8, 'The midterms were on November third. He said the war would end right after.', .58, .4, kind='event', date='NOV 3, 2026', head='Midterm elections', tag='DAY 249')
line(8, 'Will it end soon this time?', .66, .5, kind='number', big='WILL IT END SOON THIS TIME?', sub='', small=1, q=1)
line(8, 'Tell us in the comments.', .6, .5, kind='number', big='TELL US IN THE COMMENTS', sub='', small=1)
line(8, 'Follow Chain Secrets. Every chart hides a story.', .7, .3, kind='end')

CHUNKS = sorted({x['c'] for x in L})
CHAPTER_GAP = 0.9          # silence between chapters (the chapter card whoosh sits here)
