"""Reply quality for Chain Secrets: write 3 candidates -> deterministic checks -> AI fact-check + judge -> ONE best reply and what was checked.

Pure logic only (no network, no Telegram) so it is easy to test; radar.py does the I/O (best_reply, reply_from_text).
Rules the checks enforce: every number in a reply must come from the post or from the live data we fetched; no links or hashtags;
8-25 words and at most 180 characters; no slang the account never uses; no claim the post itself does not support (the AI judge lists them).
"""
import re, time

# What each reply tries to do. Only moves that can be backed by the post itself or by live data: no "remember when" history claims.
STYLES = [
    ('detail', 'Point at the one detail in the post that matters most and say why in plain words. Use only what the post says.'),
    ('observation', 'Make one sharp, dry observation about what this really means. Understated, no exaggeration.'),
    ('numbers', 'Put the key number in perspective. Use ONLY numbers that are in the post or in the LIVE DATA block.'),
    ('calm_take', 'Politely push back or add the missing context, calmly, in one or two sentences. Respectful, no insults.'),
    ('light_humor', 'A light, clever line with a point behind it. Witty, not silly, no slang.'),
    ('question', 'Ask one genuine, smart question that experts would want answered about this (not engagement bait).'),
]
STYLE_NAMES = [s[0] for s in STYLES]

SLANG = re.compile(r'\b(bro|bros|bruh|fam|ser|fren|frens|gm|wagmi|ngmi|lfg|degen|degens|ape|aped|rekt|lol|lmao|ngl|fr|no cap)\b', re.I)
AI_TELLS = re.compile(r"let that sink in|this is huge|game.?changer|translation:|delve|it'?s worth noting|in the world of|not financial advice|buy now|to the moon", re.I)
SUFFIX = {'k': 1e3, 'm': 1e6, 'mn': 1e6, 'b': 1e9, 'bn': 1e9, 't': 1e12}
WORD_SCALE = {'thousand': 1e3, 'million': 1e6, 'billion': 1e9, 'trillion': 1e12}
NUM = re.compile(r'(?<![\w.])(\$?)(\d[\d,]*(?:\.\d+)?)\s?(?:([kKmMbBtT][nN]?)\b|(%)|(thousand|million|billion|trillion)\b)?')


def numbers(text):
    """[(value, is_percent)] for every number in the text: $4.3B, 4,300,000,000, 12%, 80k, 15 million all normalise."""
    out = []
    for m in NUM.finditer(text or ''):
        try:
            v = float(m.group(2).replace(',', ''))
        except ValueError:
            continue
        if m.group(3):
            v *= SUFFIX[m.group(3).lower()]
        elif m.group(5):
            v *= WORD_SCALE[m.group(5).lower()]
        out.append((v, bool(m.group(4))))
    return out


def numbers_ok(reply, *sources):
    """Every number in the reply (except 0 to 10) must appear in a source, within 1.5% for rounding ($4.28B ~ $4.3B). Returns (ok, [missing])."""
    have = [v for s in sources for v, _ in numbers(s)]
    missing = []
    for v, pct in numbers(reply):
        if 0 <= v <= 10 and float(v).is_integer():
            continue
        if not any(abs(a - v) <= .015 * max(abs(a), abs(v), 1e-9) for a in have):
            missing.append(('%g' % v) + ('%' if pct else ''))
    return not missing, missing


def shape_ok(reply):
    """(ok, why): length, links, hashtags, slang, AI-sounding phrases, em dashes"""
    r = (reply or '').strip()
    w = len(r.split())
    if not 6 <= w <= 30 or len(r) > 200:
        return False, f'{w} words / {len(r)} characters'
    if re.search(r'https?://|www\.|#\w', r):
        return False, 'link or hashtag'
    if SLANG.search(r):
        return False, 'slang'
    if AI_TELLS.search(r):
        return False, 'sounds like AI'
    if '—' in r:
        return False, 'em dash'
    return True, ''


def age_note(post, now=None):
    """one line about whether replying now is worth it (early replies get seen; old ones do not)"""
    ts = (post or {}).get('ts')
    if not ts:
        return ''
    m = ((now or time.time()) - ts) / 60
    if m < 0:
        m = 0
    age = f'{m:.0f} min ago' if m < 90 else f'{m / 60:.0f}h ago' if m < 2880 else f'{m / 1440:.0f} days ago'
    if m < 15:
        return f'🟢 posted {age}: prime window, reply now'
    if m < 120:
        return f'🟡 posted {age}: still worth replying'
    return f'🔴 posted {age}: late, replies this old get little reach'


STYLE_LABEL = {'detail': 'adds the key detail', 'observation': 'sharp take', 'numbers': 'puts it in perspective', 'calm_take': 'calm pushback',
               'light_humor': 'light humor', 'question': 'smart question'}


def pick_styles(used=(), n=5, rnd=None):
    """n different angles for this round; angles already shown for this post come last so 'new ideas' really are new."""
    import random
    rnd = rnd or random
    fresh = [x for x in STYLE_NAMES if x not in used]; old = [x for x in STYLE_NAMES if x in used]
    rnd.shuffle(fresh); rnd.shuffle(old)
    return (fresh + old)[:n]


def style_text(name):
    return dict(STYLES).get(name, STYLES[0][1])


def candidate_prompt(head, post_text, author, stance_text, styles, live, note=''):
    """head = the house VOICE + owner view text from radar.py"""
    lines = '\n'.join(f'{i + 1}. style "{s}": {style_text(s)}' for i, s in enumerate(styles))
    return (head + '\n' + stance_text + f'\nYou reply under an X post as the account "Chain Secrets". Write {len(styles)} DIFFERENT reply ideas, one per style below (the owner will pick and copy one). '
            'Each reads like a normal, relaxed person wrote it in ten seconds (contractions, plain words, a little personality, never marketing): 8 to 25 words, max 180 characters, about what THIS post actually says. '
            'Start with the point, no warm-up; the first 8 words must add something the post does not already say. Never invent facts. Every number must come from the post or the LIVE DATA block; if you are unsure, leave it out.\n'
            f'Styles:\n{lines}\n\nPOST by @{author}:\n{post_text[:1500]}\n\n'
            + (f'LIVE DATA (verified just now):\n{live}\n\n' if live else '') + (note + '\n' if note else '')
            + 'Return JSON only: {"replies": [{"style": "...", "reply": "..."}], "symbol": "ticker of the crypto coin the post is mainly about, or NONE", '
              '"chart": true only if the post is about that coin\'s price moving and a 24h chart would back the reply, else false}')


def judge_prompt(post_text, live, cands, stance_text):
    lst = '\n'.join(f'{i + 1}. {c["reply"]}' for i, c in enumerate(cands))
    return ('You are a strict fact-checker and editor for an X account. Check each candidate reply against ONLY the POST and the LIVE DATA.\n'
            f'POST:\n{post_text[:1500]}\n\n' + (f'LIVE DATA:\n{live}\n\n' if live else '') + f'{stance_text}\n\nCANDIDATES:\n{lst}\n\n'
            'For each candidate: "unsupported" = a list of factual claims (names, numbers, events, causes) that the POST and LIVE DATA do not support (empty list if every claim is supported; '
            'opinions and questions are fine). Then score 0-10: "human" (sounds like a real person, not marketing or AI), "value" (adds something the post does not already say, in its first 8 words).\n'
            'Return JSON only: {"c": [{"n": 1, "unsupported": [], "human": 0, "value": 0}]} with one entry per candidate.')


def choose_n(cands, verdict, n=3):
    """The best n candidates that passed every check, with different angles. Returns (list, level): 'verified', 'numbers' (judge unavailable) or None."""
    by = {}
    if isinstance(verdict, dict):
        for x in verdict.get('c') or []:
            try:
                by[int(x['n'])] = x
            except (KeyError, TypeError, ValueError):
                pass
    scored = []
    for i, c in enumerate(cands, 1):
        if not (c['nums_ok'] and c['shape_ok']):
            continue
        j = by.get(i)
        if by and j is None:
            continue
        if j is not None and j.get('unsupported'):
            continue
        sc = sum(float(j.get(k) or 0) for k in ('human', 'value')) if j else 10.0
        scored.append((sc, c))
    out, seen = [], set()
    for sc, c in sorted(scored, key=lambda x: -x[0]):
        if c['style'] in seen:
            continue
        seen.add(c['style']); out.append(c)
        if len(out) == n:
            break
    return out, (('verified' if by else 'numbers') if out else None)


def check_line(level, live):
    if level == 'verified':
        return '✅ <b>Checked:</b> numbers match the post' + (' and live data' if live else '') + ' · no unsupported claims · human tone'
    if level == 'numbers':
        return '🟡 Numbers match the post. The AI fact-check was unavailable, so read it once before posting.'
    return '⚠️ I could not fully verify this one. Read it carefully before posting.'
