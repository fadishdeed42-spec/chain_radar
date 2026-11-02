"""Illustrated scene types: pictures that SHOW what the narrator is saying (phone screens, documents, routes, crowds,
buildings, votes, server racks, headline stacks). auto.py execs this file into its own namespace (it uses auto's
globals: cv helpers, P(i), hit(i), scene_end(i), ACC/ALT/BAD, fit(), cs.WORDS ...).

Every type can also take "steps": [{"word": "...", ...}] so things change on the exact spoken word."""

PAPER = (244, 240, 230); INK = (28, 30, 36); INK2 = (110, 112, 120)


def _key(w):
    return re.sub(r'[^\w$%]', '', str(w)).lower()


def wt(i, word, default=None):
    """time the narrator says `word` in scene i (first match), else default"""
    k = _key(word)
    for w in cs.WORDS:
        if w[0] == i and w[1] == k:
            return w[2]
    return default


def _steps(i, v):
    """visual.steps -> sorted list of (time, step) using spoken words; steps without a found word spread evenly"""
    st = v.get('steps') or []
    out, s0, e = [], P(i) + .3, scene_end(i) - .3
    for n, s in enumerate(st):
        t0 = wt(i, s.get('word', ''), None)
        if t0 is None: t0 = lerp(s0, e, (n + 1) / (len(st) + 1))
        out.append((t0, s))
    return sorted(out, key=lambda x: x[0])


def typed(text, p):
    n = int(round(len(text) * clamp(p)))
    return text[:n]


# ---------------------------------------------------------------- phone app screen
def sc_app(cv, t, i, v, a):
    """phone with an app screen: app bar, a field (typed), then at the hit the field shows the shocking value and a
    notification drops in. v: app, title, field, value, value2, alert, sub"""
    h = hit(i)
    hook = SCN[i]['role'] == 'hook'
    if hook: h = min(h, P(i) + 1.0)                                      # the hook shows the shock right away
    q = back(seg(t, P(i), P(i) + (.2 if hook else .45)))
    if q <= 0: return
    x0, x1, y0 = 250, 830, 330 + (1 - q) * 300
    y1 = y0 + 1060
    cv.rect(x0 - 18, y0 - 18, x1 + 18, y1 + 18, (58, 64, 80), a, r=70)          # body
    cv.rect(x0, y0, x1, y1, (246, 247, 250), a, r=56)                          # screen
    cv.rect(W / 2 - 70, y0 + 18, W / 2 + 70, y0 + 44, (58, 64, 80), a, r=13)   # notch
    cv.rect(x0, y0 + 70, x1, y0 + 170, ACC, a)                                 # app bar
    cv.text(x0 + 40, y0 + 120, str(v.get('app', 'APP')).upper()[:16], 'black', 40, WHITE, a, anchor='lm', track=3)
    cv.text(x0 + 40, y0 + 250, str(v.get('title', '')).upper()[:20], 'black', 46, INK, a, anchor='lm')
    if v.get('sub'):
        cv.text(x0 + 40, y0 + 310, str(v['sub'])[:30], 'bold', 32, INK2, a, anchor='lm')
    # the field
    fy = y0 + 420
    cv.text(x0 + 40, fy - 30, str(v.get('field', 'AMOUNT')).upper()[:18], 'bold', 28, INK2, a, anchor='lm', track=4)
    flip = t >= h - .05
    bad = flip and v.get('value2')
    cv.rect(x0 + 30, fy, x1 - 30, fy + 130, (255, 236, 238) if bad else (236, 240, 246), a, r=18)
    val = str(v.get('value2') if bad else v.get('value', ''))
    shown = val if bad else typed(val, seg(t, P(i) + (.1 if hook else .5), P(i) + (.6 if hook else 1.4)))
    cur = '|' if (not bad and int(t * 2.5) % 2 == 0) else ''
    sz = fit(val, 'black', 76, x1 - x0 - 110)
    cv.text(x0 + 60, fy + 65, shown + cur, 'black', sz, BAD if bad else INK, a, anchor='lm', tnum=True,
            scale=lerp(1.25, 1, out3(seg(t, h - .05, h + .25))) if bad else 1.0)
    # button
    cv.rect(x0 + 30, y1 - 190, x1 - 30, y1 - 80, ACC if not flip else (60, 180, 110), a, r=55)
    cv.text(W / 2, y1 - 135, 'SENT' if flip else str(v.get('button', 'SEND')).upper(), 'black', 44, WHITE, a, anchor='cm')
    # notification banner
    if flip and v.get('alert'):
        p = out3(seg(t, h, h + .4))
        by = y0 - 200 + 280 * p
        cv.rect(x0 - 40, by, x1 + 40, by + 150, (32, 36, 48), a * .97, r=34)
        cv.circle(x0 + 30, by + 75, 34, ACC, a)
        cv.text(x0 + 90, by + 50, str(v.get('alert_from', v.get('app', ''))).upper()[:22], 'bold', 26, (170, 176, 190), a, anchor='lm', track=3)
        cv.text(x0 + 90, by + 100, str(v['alert'])[:30], 'black', fit(str(v['alert'])[:30], 'black', 42, x1 - x0 - 40), WHITE, a, anchor='lm')


# ---------------------------------------------------------------- paper document
def sc_doc(cv, t, i, v, a):
    """a paper document (court order, proposal, passport page): header, lines typed in as they are spoken, stamp at the hit.
    v: head, title, lines[], stamp, seal"""
    h = hit(i)
    q = out3(seg(t, P(i), P(i) + .5))
    if q <= 0: return
    rot = (1 - q) * .08
    x0, x1, y0, y1 = 170, 910, 330 + (1 - q) * 200, 1330 + (1 - q) * 200
    cv.rect(x0 + 14, y0 + 18, x1 + 14, y1 + 18, (0, 0, 0), a * .35, r=10)
    cv.rect(x0, y0, x1, y1, PAPER, a, r=10)
    cv.text(W / 2, y0 + 70, str(v.get('head', '')).upper()[:34], 'bold', 26, INK2, a, anchor='cm', track=6)
    cv.line([(x0 + 60, y0 + 110), (x1 - 60, y0 + 110)], INK2, 2, a)
    title = str(v.get('title', '')).upper()
    for k, ln in enumerate(wrap(title, 18)[:2]):
        cv.text(W / 2, y0 + 175 + k * 70, ln, 'black', fit(ln, 'black', 60, x1 - x0 - 100), INK, a, anchor='cm')
    lines = [str(x) for x in (v.get('lines') or [])][:6]
    st = _steps(i, {'steps': [{'word': w} for w in (v.get('at') or [])]}) if v.get('at') else []
    for k, ln in enumerate(lines):
        t0 = st[k][0] if k < len(st) else P(i) + .45 + k * min(.55, max(.25, (h - P(i) - .6) / max(1, len(lines))))
        p = seg(t, t0 - .1, t0 + .6)
        yy = y0 + 360 + k * 92
        if p <= 0:
            cv.rect(x0 + 70, yy - 8, x0 + 70 + (x1 - x0 - 140) * (.55 + .3 * ((k * 37) % 10) / 10), yy + 8, (215, 210, 198), a, r=8)
            continue
        cv.text(x0 + 70, yy, typed(ln, p), 'bold', fit(ln, 'bold', 44, x1 - x0 - 140), INK, a, anchor='lm')
    if v.get('seal'):
        cv.ring(x1 - 150, y1 - 150, 80, (170, 40, 50), 6, a * .8)
        cv.text(x1 - 150, y1 - 150, str(v['seal']).upper()[:8], 'black', 30, (170, 40, 50), a * .8, anchor='cm')
    if t >= h - .1 and v.get('stamp'):
        stamp(cv, t, h - .1, str(v['stamp']).upper(), W / 2, y1 - 210, fit(str(v['stamp']).upper(), 'black', 100, 640), BAD, a)


# ---------------------------------------------------------------- route (escape, transfer between places)
def sc_route(cv, t, i, v, a):
    """two (or three) places joined by a dashed arc; a plane flies along it from the scene start to the hit.
    v: from, to, via, label"""
    h = hit(i)
    pts = [(200, 1150), (540, 560), (880, 980)] if v.get('via') else [(200, 1150), (880, 700)]
    names = [v.get('from', 'A'), v.get('via'), v.get('to', 'B')] if v.get('via') else [v.get('from', 'A'), v.get('to', 'B')]
    q = seg(t, P(i), P(i) + .4)
    # path points (quadratic arcs between stops)
    path = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        cx, cy = (ax + bx) / 2, min(ay, by) - 220
        for k in range(40):
            u = k / 39
            path.append(((1 - u) ** 2 * ax + 2 * (1 - u) * u * cx + u * u * bx, (1 - u) ** 2 * ay + 2 * (1 - u) * u * cy + u * u * by))
    p = smooth(seg(t, P(i) + .3, h))
    n = max(2, int(len(path) * p))
    for k in range(0, len(path) - 1, 2):
        cv.line([path[k], path[k + 1]], (90, 98, 120), 4, a * q)
    if n > 1:
        cv.line(path[:n], ACC, 7, a)
    for k, ((x, y), nm) in enumerate(zip(pts, names)):
        reached = p >= k / max(1, len(pts) - 1) - .01
        cv.glow(x, y, 60, ACC if reached else MUTED, .35 * a * q)
        cv.circle(x, y, 22, ACC if reached else (110, 118, 136), a * q)
        cv.circle(x, y, 9, BG, a * q)
        cv.text(x, y + 70 if y > 800 else y - 70, str(nm).upper()[:12], 'black', 54, TXT if reached else MUTED, a * q, anchor='cm')
    px, py = path[n - 1]; qx, qy = path[min(len(path) - 1, n)]
    ang = math.atan2(qy - py, qx - px)
    plane(cv, px, py, .55, a, col=WHITE, ang=ang)
    if v.get('label') and t >= h - .1:
        stamp(cv, t, h - .1, str(v['label']).upper(), W / 2, 1330, fit(str(v['label']).upper(), 'black', 80, 760), BAD, a)


# ---------------------------------------------------------------- crowd (victims, queues, holders)
def sc_crowd(cv, t, i, v, a):
    """rows of little people filling the screen, the number counting up to the hit. v: value, label, cols, rows"""
    h = hit(i)
    cols, rows = int(v.get('cols', 9)), int(v.get('rows', 7))
    tot = cols * rows
    p = out3(seg(t, P(i) + .1, h))
    shown = int(tot * p)
    for k in range(tot):
        if k >= shown: break
        r_, c_ = divmod(k, cols)
        x = 130 + c_ * (820 / (cols - 1)); y = 700 + r_ * 92
        col = BAD if (v.get('mark') and k == tot - 1) else (150, 160, 180)
        cv.circle(x, y - 22, 17, col, a * .95)
        cv.rect(x - 22, y, x + 22, y + 40, col, a * .95, r=14)
    try: val = float(v.get('value', 0))
    except (TypeError, ValueError): val = 0
    num = fmt_num(round(val * p) if val == int(val) else val * p, str(v.get('prefix', '')), str(v.get('suffix', '')), abs(val))
    counter(cv, num, 470, fit(fmt_num(val, '', ''), 'black', 150, 900), ACC, a, glow=p > 0)
    if v.get('label'):
        cv.text(W / 2, 580, str(v['label']).upper(), 'black', fit(str(v['label']).upper(), 'black', 46, 960), MUTED, a, anchor='cm', track=8)


# ---------------------------------------------------------------- facility (secret lab, exchange HQ, court)
def _radiation(cv, x, y, r, a):
    cv.circle(x, y, r, (255, 206, 40), a)
    for k in range(3):
        ang = -math.pi / 2 + k * 2 * math.pi / 3
        pts = [(x, y)]
        for u in range(13):
            th = ang - .5 + u / 12
            pts.append((x + math.cos(th) * r * .85, y + math.sin(th) * r * .85))
        cv.poly(pts, (30, 30, 30), a)
    cv.circle(x, y, r * .22, (255, 206, 40), a); cv.circle(x, y, r * .14, (30, 30, 30), a)


def sc_facility(cv, t, i, v, a):
    """a building with a sign (radiation / bank / court), a fence and a sweeping searchlight; stamp at the hit.
    v: name, sign ('radiation'|'bank'|'none'), tag"""
    h = hit(i)
    q = out3(seg(t, P(i), P(i) + .5))
    if q <= 0: return
    gy = 1180
    # searchlight
    sw = math.sin(t * 1.3) * .5
    cv.poly([(W / 2, 520), (W / 2 + math.sin(sw - .18) * 1200, 520 - math.cos(sw - .18) * 1200),
             (W / 2 + math.sin(sw + .18) * 1200, 520 - math.cos(sw + .18) * 1200)], (255, 240, 200), .06 * a * q)
    cv.rect(180, gy - 420 * q, 900, gy, (52, 58, 74), a, r=8)                 # main block
    cv.rect(400, gy - 560 * q, 680, gy - 400 * q, (62, 68, 86), a, r=6)       # tower
    for r_ in range(3):
        for c_ in range(6):
            lit = ((r_ * 7 + c_ * 3 + int(t * 1.5)) % 5) == 0
            cv.rect(230 + c_ * 110, gy - 360 * q + r_ * 105, 290 + c_ * 110, gy - 310 * q + r_ * 105, GOLD if lit else (34, 38, 50), a)
    sign = v.get('sign', 'radiation')
    if sign == 'radiation': _radiation(cv, W / 2, gy - 480 * q, 62, a * q)
    for k in range(17):                                                        # fence
        x = 60 + k * 60
        cv.line([(x, gy + 10), (x, gy + 130)], (120, 126, 140), 4, a)
    for yy in (gy + 40, gy + 100):
        cv.line([(60, yy), (1020, yy)], (120, 126, 140), 3, a)
    if v.get('name'):
        cv.text(W / 2, 440, str(v['name']).upper(), 'black', fit(str(v['name']).upper(), 'black', 90, 900), TXT, a * q, anchor='cm')
    if v.get('tag') and t >= h - .1:
        stamp(cv, t, h - .1, str(v['tag']).upper(), W / 2, 1380, fit(str(v['tag']).upper(), 'black', 80, 800), BAD, a)


# ---------------------------------------------------------------- server racks (supercomputer, mining farm)
def sc_servers(cv, t, i, v, a):
    """racks of blinking machines; at the hit the label lands (e.g. '1 PETAFLOP'). v: label, sub, coin(bool)"""
    h = hit(i)
    q = out3(seg(t, P(i), P(i) + .5))
    for k in range(4):
        x0 = 120 + k * 220; y0 = 520 + (1 - q) * 300
        cv.rect(x0, y0, x0 + 180, y0 + 640, (40, 46, 60), a, r=10)
        for r_ in range(12):
            yy = y0 + 30 + r_ * 50
            cv.rect(x0 + 16, yy, x0 + 164, yy + 34, (26, 30, 40), a, r=4)
            for d in range(4):
                on = ((r_ * 5 + d * 3 + k * 7 + int(t * 8)) % 6) < 2
                cv.circle(x0 + 34 + d * 22, yy + 17, 5, (ACC if d % 2 else (60, 230, 120)) if on else (60, 66, 80), a)
    if v.get('coin') and t >= h - .3:
        for k in range(6):
            u = (t - h + .3 + k * .23) % 1.4 / 1.4
            coin(cv, 200 + k * 140, 1180 - u * 700, 34, a * (1 - u) * .9)
    if t >= h - .1 and v.get('label'):
        lab = str(v['label']).upper()
        slam(cv, t, h - .1, lab, 400, fit(lab, 'black', 120, 980), ACC, a)
        if v.get('sub'):
            cv.text(W / 2, 480, str(v['sub']).upper(), 'black', fit(str(v['sub']).upper(), 'black', 40, 900), TXT, a * seg(t, h + .2, h + .5), anchor='cm')


# ---------------------------------------------------------------- vote / ballot
def sc_vote(cv, t, i, v, a):
    """a proposal card with a YES bar filling to the hit, then PASSED. v: title, sub, pct, stamp"""
    h = hit(i)
    q = out3(seg(t, P(i), P(i) + .4))
    if q <= 0: return
    y0 = 420 + (1 - q) * 200
    cv.rect(130, y0, 950, y0 + 760, PANEL, a, r=36)
    cv.text(190, y0 + 80, str(v.get('title', 'PROPOSAL')).upper()[:22], 'black', 58, TXT, a, anchor='lm')
    if v.get('sub'): cv.text(190, y0 + 150, str(v['sub'])[:34], 'bold', 34, MUTED, a, anchor='lm')
    pct = float(v.get('pct', 100)) / 100
    p = out3(seg(t, P(i) + .5, h)) * pct
    for k, (lab, val, col) in enumerate((('YES', p, ALT if ALT != ACC else UP), ('NO', 0.0, BAD))):
        yy = y0 + 300 + k * 170
        cv.text(190, yy - 50, lab, 'black', 40, TXT, a, anchor='lm')
        cv.rect(190, yy, 890, yy + 70, (34, 40, 56), a, r=35)
        if val > .01: cv.rect(190, yy, 190 + 700 * val, yy + 70, col, a, r=35)
        cv.text(890, yy - 50, f'{val * 100:.0f}%', 'black', 40, col, a, anchor='rm', tnum=True)
    if t >= h - .1:
        stamp(cv, t, h - .1, str(v.get('stamp', 'PASSED')).upper(), W / 2, y0 + 660, 92, BAD, a)


# ---------------------------------------------------------------- stacked headlines (reading = watch time)
def sc_news(cv, t, i, v, a):
    """2-3 real headlines land one after another on their spoken words. v: items[{src, headline, word?}], kicker"""
    items = (v.get('items') or [])[:3]
    st = _steps(i, {'steps': [{'word': it.get('word', '')} for it in items]})
    for k, it in enumerate(items):
        t0 = st[k][0] if k < len(st) else P(i) + .3 + k * .8
        if k == 0: t0 = min(t0, P(i) + .3)
        p = back(seg(t, t0 - .15, t0 + .3))
        if p <= 0: continue
        y0 = 360 + k * 330
        lines = wrap(str(it.get('headline', '')), 30)[:3]
        hh = 110 + 62 * len(lines)
        x0 = lerp(-900, 70, out3(seg(t, t0 - .15, t0 + .3)))
        cv.rect(x0 + 10, y0 + 12, x0 + W - 130, y0 + hh + 12, (0, 0, 0), a * .3, r=22)
        cv.rect(x0, y0, x0 + W - 140, y0 + hh, (246, 247, 250), a, r=22)
        cv.rect(x0, y0, x0 + 14, y0 + hh, BAD, a, r=7)
        cv.text(x0 + 44, y0 + 50, str(it.get('src', '')).upper()[:30], 'black', 30, (190, 40, 60), a, anchor='lm', track=4)
        cv.text(x0 + W - 170, y0 + 50, str(it.get('kind', 'HEADLINE')).upper(), 'bold', 24, (120, 128, 140), a, anchor='rm', track=3)
        for j, ln in enumerate(lines):
            cv.text(x0 + 44, y0 + 112 + j * 62, ln, 'black', 48, (16, 20, 28), a, anchor='lm')


ILLUS = {'app': sc_app, 'doc': sc_doc, 'route': sc_route, 'crowd': sc_crowd, 'facility': sc_facility,
         'servers': sc_servers, 'vote': sc_vote, 'news': sc_news}
