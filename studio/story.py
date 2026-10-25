"""Storyboard -> voice job + timing for the automatic Chain Secrets Shorts.

A storyboard (written by Gemini, checked here) is a list of scenes. Each scene has a DISPLAY line (what the captions show,
with real digits: "$4B", "2017", "Oct 25") and a visual. The narrator must say every word, so each display token is turned
into SPOKEN words ("four billion dollars", "twenty seventeen", "October twenty-fifth") while remembering how many spoken
words belong to each token. That count is what keeps captions and visual hits locked to the voice.
"""
import json, re, math

ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()
ORD = {'one': 'first', 'two': 'second', 'three': 'third', 'five': 'fifth', 'eight': 'eighth', 'nine': 'ninth', 'twelve': 'twelfth'}
MONTHS = {'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April', 'may': 'May', 'jun': 'June', 'jul': 'July',
          'aug': 'August', 'sep': 'September', 'sept': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'}
SPELL = {'BTC': 'bitcoin', 'ETH': 'ether', 'FBI': 'F B I', 'SEC': 'S E C', 'CEO': 'C E O', 'NFT': 'N F T', 'NFTS': 'N F Ts',
         'DAO': 'dow', 'USD': 'dollars', 'DOJ': 'D O J', 'IRS': 'I R S', 'ETF': 'E T F', 'ETFS': 'E T Fs', 'ATM': 'A T M',
         'DEFI': 'Dee-fye', 'IPO': 'I P O', 'USDT': 'tether', 'USDC': 'U S D C', 'CFTC': 'C F T C', 'XRP': 'X R P', 'FTX': 'F T X',
         'AI': 'A I', 'US': 'U S', 'UK': 'U K', 'UAE': 'U A E', 'NYC': 'New York', 'BNB': 'B N B', 'SOL': 'sol', 'OK': 'okay'}
ABBR = {'mt.': 'Mount', 'mt': 'Mount', 'vs': 'versus', 'vs.': 'versus', 'st.': 'Saint', 'dr.': 'Doctor', 'mr.': 'Mister',
        'mrs.': 'Missus', 'u.s.': 'U S', 'approx.': 'about', '&': 'and', 'w/': 'with', 'jr.': 'Junior'}
WORDS = {'NASA', 'FOMO', 'HODL', 'LUNA', 'DOGE', 'PEPE', 'APE', 'SHIB', 'GOX', 'MOON', 'REKT', 'FUD', 'WAGMI', 'BOOM', 'GONE',
         'LIFE', 'FAKE', 'SCAM', 'ZERO', 'HACK', 'RICH', 'BROKE', 'WHY', 'HOW', 'WHO', 'NOT', 'ALL', 'BUY', 'SELL', 'NEW', 'TRON', 'COIN',
         'NO', 'YES', 'GO', 'UP', 'WE', 'ME', 'IT', 'IS', 'BE', 'BY', 'SO', 'OR', 'IF', 'IN', 'ON', 'AT', 'TO', 'OF', 'AN', 'AND', 'THE',
         'BIG', 'WIN', 'WON', 'RUN', 'END', 'TOP', 'OUT', 'OFF', 'ONE', 'TWO', 'TEN', 'BAD', 'MAD', 'WOW', 'HUGE', 'NEXT', 'LAST', 'ONLY',
         'EVER', 'DEAD', 'REAL', 'LIES', 'LOST', 'MY', 'HIS', 'HER', 'YOU', 'WAS', 'ARE', 'HAS', 'DID', 'CAN', 'NOW', 'JUST', 'THIS',
         'THAT', 'THEN', 'BOTH', 'MUCH', 'MANY', 'SOME', 'MOST', 'VERY', 'ALSO', 'EVEN', 'STOP', 'HELP', 'BANK', 'CASH', 'GOLD', 'KING'}
SCALE = [(1e12, 'trillion'), (1e9, 'billion'), (1e6, 'million'), (1e3, 'thousand')]


def int_words(n):
    n = int(n)
    if n < 0:
        return 'minus ' + int_words(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ('-' + ONES[n % 10] if n % 10 else '')
    if n < 1000:
        return ONES[n // 100] + ' hundred' + (' ' + int_words(n % 100) if n % 100 else '')
    for v, name in SCALE:
        if n >= v:
            v = int(v)
            return int_words(n // v) + ' ' + name + (' ' + int_words(n % v) if n % v else '')
    return str(n)


def ordinal(n):
    w = int_words(n)
    head, sep, last = w.rpartition('-') if '-' in w.split(' ')[-1] else w.rpartition(' ')
    if last in ORD:
        last = ORD[last]
    elif last.endswith('y'):
        last = last[:-1] + 'ieth'
    else:
        last += 'th'
    return head + sep + last


def year_words(y):
    y = int(y)
    if 2000 <= y <= 2009:
        return 'two thousand' + (' ' + ONES[y - 2000] if y > 2000 else '')
    hi, lo = divmod(y, 100)
    return int_words(hi) + ' ' + ('hundred' if lo == 0 else ('oh ' + ONES[lo] if lo < 10 else int_words(lo)))


def dec_words(s):
    """'3.4' -> 'three point four', '1.25' -> 'one point two five'"""
    a, _, b = s.partition('.')
    out = int_words(int(a or 0))
    if b:
        out += ' point ' + ' '.join(ONES[int(c)] for c in b)
    return out


def money_words(v):
    """Human style: 4e9 -> 'four billion', 3.36e9 -> 'three point three six billion', 19666 -> 'nineteen thousand six hundred sixty-six'"""
    if v >= 1e6:
        for sv, name in SCALE[:3]:
            if v >= sv:
                x = v / sv
                s = f'{x:.2f}'.rstrip('0').rstrip('.')
                return dec_words(s) + ' ' + name
    if v != int(v):
        d, c = int(v), round((v - int(v)) * 100)
        return int_words(d) + (f' dollars and {int_words(c)} cents' if c else '')
    return int_words(int(v))


SUFFIX = {'k': 1e3, 'm': 1e6, 'mn': 1e6, 'b': 1e9, 'bn': 1e9, 't': 1e12}


def spoken(token, nxt='', respell=None):
    """One display token -> spoken text (may be several words). Trailing punctuation stays on the last spoken word."""
    respell = respell or {}
    m = re.match(r'^(["\'(\[]*)(.*?)([.,!?:;"\')\]…]*)$', token)
    pre, core, post = m.group(1), m.group(2), m.group(3)
    post = post.replace('…', '...')
    if not core:
        return ''
    key = core.strip()
    if token.lower() in ABBR:
        return ABBR[token.lower()]
    for k, v in respell.items():                                            # names the voice must say differently
        if key.lower() == k.lower():
            return v + post
    if key.upper() in SPELL and (key.isupper() or key.upper() in ('DEFI',)):
        return SPELL[key.upper()] + post
    if key.isalpha() and key.isupper() and 2 <= len(key) <= 4 and key not in WORDS:      # DEA, CIA, OKX -> letter by letter
        return ' '.join(key) + post
    nxt_l = re.sub(r'[^a-z]', '', nxt.lower())
    big_next = nxt_l in ('million', 'billion', 'trillion', 'thousand')
    # $4B, $1.5M, $19,666, $4,000,000,000, $15 (million)
    mm = re.match(r'^-?\$(\d[\d,]*(?:\.\d+)?)([kKmMbBtT][nN]?)?$', key)
    if mm:
        v = float(mm.group(1).replace(',', '')) * SUFFIX.get((mm.group(2) or '').lower(), 1)
        if big_next:                                                        # "$15 million": say "fifteen", "million dollars" comes next
            return dec_words(mm.group(1).replace(',', '')) + post
        return money_words(v) + ' dollars' + post
    mm = re.match(r'^(\d[\d,]*(?:\.\d+)?)([kKmMbBtT][nN]?)$', key)          # 50K, 3.36B (no $)
    if mm:
        v = float(mm.group(1).replace(',', '')) * SUFFIX[mm.group(2).lower()]
        return money_words(v) + post
    mm = re.match(r'^([+-]?)(\d[\d,]*(?:\.\d+)?)%$', key)                    # 40%, -54%
    if mm:
        return ('minus ' if mm.group(1) == '-' else 'plus ' if mm.group(1) == '+' else '') + dec_words(mm.group(2).replace(',', '')) + ' percent' + post
    mm = re.match(r'^(\d+(?:\.\d+)?)[xX]$', key)                            # 3.4x
    if mm:
        return dec_words(mm.group(1)) + ' times' + post
    mm = re.match(r'^(\d+)(st|nd|rd|th)$', key, re.I)                       # 25th
    if mm:
        return ordinal(int(mm.group(1))) + post
    mm = re.match(r"^(\d{4})s$", key)                                       # 1990s
    if mm:
        w = year_words(mm.group(1))
        return (w[:-1] + 'ies' if w.endswith('y') else w + 's') + post
    mm = re.match(r"^'(\d{2})$", key)                                       # '17
    if mm:
        return 'twenty ' + int_words(int(mm.group(1))) + post
    if re.match(r'^(1[89]|20)\d{2}$', key) and not big_next:               # a year
        return year_words(key) + post
    mm = re.match(r'^(\d[\d,]*)(\.\d+)?$', key)                             # plain number
    if mm:
        return dec_words(key.replace(',', '')) + post
    mm = re.match(r'^(\d+)[-/](\d+)$', key)                                  # 24/7, 9-5
    if mm:
        return int_words(int(mm.group(1))) + ' ' + int_words(int(mm.group(2))) + post
    if key.lower().rstrip('.') in MONTHS and len(key) <= 5 and re.match(r'^\d', nxt or ''):
        return MONTHS[key.lower().rstrip('.')] + post                      # "Oct 25" -> "October twenty-fifth"
    if re.match(r'^\d', key):                                               # leftovers with digits: read digits
        return ' '.join(ONES[int(c)] if c.isdigit() else c for c in key if c.isalnum()) + post
    return pre + key.replace('&', 'and') + post


def plan_line(line, respell=None, after_month=False):
    """Display line -> [(display_token, [spoken words])]. Day numbers after a month become ordinals."""
    toks = line.split()
    out = []
    for i, tok in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else ''
        prev = re.sub(r'[^a-z]', '', toks[i - 1].lower()) if i else ''
        core = re.sub(r'[^\d]', '', tok)
        if prev in MONTHS and core and 1 <= int(core) <= 31 and re.match(r'^\d{1,2}[.,!?:;]*$', tok):
            sp = ordinal(int(core)) + re.sub(r'^\d+', '', tok)
        else:
            sp = spoken(tok, nxt, respell)
        if re.match(r'^\$', tok) and re.sub(r'[^a-z]', '', nxt.lower()) in ('million', 'billion', 'trillion', 'thousand'):
            pass
        words = sp.split()
        if out and re.match(r'^-?\$\d', toks[i - 1]) and re.sub(r'[^a-z]', '', tok.lower()) in ('million', 'billion', 'trillion', 'thousand'):
            m = re.match(r'^([a-zA-Z]+)(.*)$', tok)                         # "$15 million." -> "million dollars." / "$5 million reward" -> "million dollar reward"
            adj = not m.group(2) and i + 1 < len(toks) and re.match(r'^[a-z]', toks[i + 1])
            words = [m.group(1).lower(), ('dollar' if adj else 'dollars') + m.group(2)]
        out.append((tok, [w for w in words if w]))
    return out


# ---------------------------------------------------------------- storyboard
TONES = ('funny', 'serious', 'mystery', 'hype')
ROLES = ('hook', 'setup', 'turn', 'twist', 'payoff', 'end')
VISUALS = ('title', 'counter', 'stamp', 'person', 'date', 'chart', 'versus', 'quote', 'list')
ICONS = ('bitcoin', 'ethereum', 'dogecoin', 'token', 'lock', 'plane', 'laptop', 'house', 'safe', 'car', 'crown', 'robot',
         'gavel', 'officer', 'person', 'calendar', 'phone', 'bank', 'fire', 'skull', 'question', 'cash')
EXAG = {  # voice emotion per role (Chatterbox exaggeration): punchier for hooks and twists, calmer for setup
    'funny':   {'hook': .9, 'setup': .75, 'turn': .8, 'twist': .95, 'payoff': .9, 'end': .6},
    'serious': {'hook': .75, 'setup': .6, 'turn': .65, 'twist': .8, 'payoff': .72, 'end': .55},
    'mystery': {'hook': .72, 'setup': .6, 'turn': .66, 'twist': .85, 'payoff': .72, 'end': .55},
    'hype':    {'hook': .95, 'setup': .8, 'turn': .85, 'twist': .95, 'payoff': .95, 'end': .65}}
CTA = 'Follow Chain Secrets. Every chart hides a story.'


def check(sb):
    """Validate + repair a storyboard. Returns (storyboard, problems). Problems that can't be repaired raise ValueError."""
    probs = []
    if not isinstance(sb, dict) or not isinstance(sb.get('scenes'), list):
        raise ValueError('no scenes')
    sb['tone'] = sb.get('tone') if sb.get('tone') in TONES else 'mystery'
    sb['respell'] = {k: v for k, v in (sb.get('respell') or {}).items() if isinstance(k, str) and isinstance(v, str)}
    sc = [s for s in sb['scenes'] if isinstance(s, dict) and str(s.get('line', '')).strip()]
    if not 4 <= len(sc) <= 8:
        raise ValueError(f'{len(sc)} scenes (need 4-8)')
    words = 0
    for i, s in enumerate(sc):
        s['line'] = re.sub(r'\s+', ' ', str(s['line']).replace('—', ', ').replace('–', '-')).strip()
        s['role'] = s.get('role') if s.get('role') in ROLES else ('hook' if i == 0 else 'end' if i == len(sc) - 1 else 'setup')
        v = s.get('visual') if isinstance(s.get('visual'), dict) else {}
        if v.get('type') not in VISUALS:
            probs.append(f'scene {i + 1}: unknown visual {v.get("type")} -> title'); v = {'type': 'title', 'text': s['line'].split('.')[0][:22].upper()}
        if v['type'] == 'chart' and not sb.get('chart'):
            probs.append(f'scene {i + 1}: chart without chart data -> title'); v = {'type': 'title', 'text': s['line'].split('.')[0][:22].upper()}
        if v.get('icon') and v['icon'] not in ICONS:
            v['icon'] = 'question'
        s['visual'] = v
        toks = [re.sub(r'[^\w$%]', '', t).lower() for t in s['line'].split()]
        h = re.sub(r'[^\w$%]', '', str(s.get('hit', ''))).lower()
        if h not in toks:                                                   # the punch must land on a real word of the line
            nums = [t for t in toks if re.search(r'\d', t)]
            s['hit'] = nums[0] if nums else toks[min(len(toks) - 1, len(toks) // 2)]
            probs.append(f'scene {i + 1}: hit word fixed -> {s["hit"]}')
        else:
            s['hit'] = h
        words += sum(len(sp) for _, sp in plan_line(s['line'], sb['respell']))
    sc[0]['role'] = 'hook'; sc[-1]['role'] = 'end'
    sb['scenes'] = sc
    secs = words / 2.85 + len(sc) * .4 + 4                                    # house pace + gaps + CTA
    if secs > 62:
        raise ValueError(f'script too long (~{secs:.0f}s, max ~55s)')
    sb['est_secs'] = round(secs)
    ch = sb.get('chart')
    if ch:
        if not (isinstance(ch, dict) and re.match(r'^\d{4}-\d{2}-\d{2}$', str(ch.get('start', ''))) and re.match(r'^\d{4}-\d{2}-\d{2}$', str(ch.get('end', '')))):
            probs.append('bad chart spec -> dropped'); sb['chart'] = None
            for s in sc:
                if s['visual']['type'] == 'chart':
                    s['visual'] = {'type': 'title', 'text': s['line'].split('.')[0][:22].upper()}
        else:
            ch['symbol'] = re.sub(r'[^A-Z0-9]', '', str(ch.get('symbol', 'BTC')).upper()) or 'BTC'
    return sb, probs


def voice_job(sb):
    """Storyboard -> cvoice json (spoken text per scene + emotion), plus the token plan used later for timing."""
    ex = EXAG[sb['tone']]
    scenes, plan = [], []
    for i, s in enumerate(sb['scenes']):
        pl = plan_line(s['line'], sb['respell'])
        text = ' '.join(w for _, sp in pl for w in sp)
        end = i == len(sb['scenes']) - 1
        scenes.append([text, ex['end'] if end else ex[s['role']], .55 if end else (.3 if s['role'] in ('twist', 'payoff') else .24)] + (['end'] if end else []))
        plan.append(pl)
    scenes.append([CTA, .7, .3])
    plan.append(plan_line(CTA))
    return {'engine': 'chatterbox', 'ref': 'am_liam', 'cfg': .2, 'seed': 7, 'scenes': scenes}, plan


# ---------------------------------------------------------------- timing (same output format as the hand-made bt*.py files)
def parse_srt(s):
    out = []
    for blk in s.strip().split('\n\n'):
        ln = blk.strip().split('\n')
        a, b = ln[1].split(' --> ')
        f = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + float(x[6:].replace(',', '.'))
        out.append((f(a), f(b), ' '.join(ln[2:])))
    return out


GOLD_, RED_, GRN_, BLU_ = [255, 196, 46], [246, 70, 93], [38, 194, 160], [64, 120, 255]
NEG = re.compile(r'hack|stole|steal|lost|lose|crash|scam|fraud|fake|gone|vanish|dead|died|prison|jail|arrest|collapse|zero|never|wrong|ban', re.I)
POS = re.compile(r'won|win|rich|record|pump|soar|surge|moon|million|billion|free|profit|up', re.I)


def build_timing(words_srt, sb, plan, out, maxg=.8, lead=.25):
    """Aligned spoken words -> captions (2-4 display words each), scene starts, the hit time per scene, CTA times."""
    words = parse_srt(words_srt)
    total = sum(len(sp) for pl in plan for _, sp in pl)
    if len(words) != total:
        raise ValueError(f'voice has {len(words)} words, plan has {total}')
    cuts = []
    for i in range(len(words) - 1):
        g0, g1 = words[i][1], words[i + 1][0]
        if g1 - g0 > maxg + .02:
            cuts.append((g0 + maxg / 2, g1 - maxg / 2))

    def M(t):
        s = t
        for a, b in cuts:
            if t >= b: s -= (b - a)
            elif t > a: s -= (t - a)
        return round(s + lead, 3)
    chunks, caps, beats, starts = [], [], {}, []
    wi = 0
    for si, pl in enumerate(plan):
        starts.append(M(words[wi][0]))
        hit = sb['scenes'][si]['hit'] if si < len(sb['scenes']) else None
        group = []

        def flush():
            nonlocal group
            if not group:
                return
            n = sum(len(sp) for _, sp, _ in group)
            first = group[0][2]
            chunks.append([M(words[first][0]), M(words[first + n - 1][1])])
            text = ' '.join(tok for tok, _, _ in group).upper()
            hl = {}
            for tok, _, _ in group:
                k = tok.upper().strip('.,!?:"')
                if re.search(r'\d', k): hl[k] = GOLD_
                elif NEG.search(k): hl[k] = RED_
                elif si == len(plan) - 1: hl[k] = GOLD_ if k in ('CHAIN', 'SECRETS.', 'SECRETS') else hl.get(k, None) or None
            caps.append([len(chunks) - 1, text, {k: v for k, v in hl.items() if v}])
            group = []
        for tok, sp, in pl:
            if hit and re.sub(r'[^\w$%]', '', tok).lower() == hit and f's{si}' not in beats:
                beats[f's{si}'] = M(words[wi][0])
            group.append((tok, sp, wi)); wi += len(sp)
            chars = sum(len(t) for t, _, _ in group)
            if len(group) >= 3 or chars >= 16 or re.search(r'[.!?:,]$', tok):
                flush()
        flush()
        beats.setdefault(f's{si}', starts[-1] + .3)
    beats['z_follow'] = starts[-1]
    every = [i for i, (tok, _) in enumerate(plan[-1]) if tok.lower().startswith('every')]
    beats['z_every'] = M(words[sum(len(sp) for pl in plan[:-1] for _, sp in pl) + sum(len(sp) for _, sp in plan[-1][:every[0]])][0]) if every else starts[-1] + 1.2
    end = M(words[-1][1]) + .35
    dur = round(end + 1.6, 2)
    para = [[round(starts[i] - (.12 if i else 0), 3) if i else 0.0, 0] for i in range(len(starts) - 1)]   # story scenes; the CTA rides on the last one
    for i in range(len(para)):
        para[i][1] = para[i + 1][0] if i + 1 < len(para) else dur
    T = {'chunks': chunks, 'dur': dur, 'beats': beats, 'para': para, 'caps': caps, 'cuts': cuts, 'lead': lead,
         'cta': round(beats['z_follow'] - .1, 3), 'cta2': beats['z_every']}
    json.dump(T, open(out, 'w'), indent=1)
    return T
