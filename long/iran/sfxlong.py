"""Sound effects keyed to the same moments the picture uses (render.py timing). python3 sfxlong.py timeline.json out.wav"""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'studio'))
import render as R
import sfx as X

def main(tlp, out):
    R.load(tlp)
    tr = np.zeros((int(R.TL['dur'] * X.SR) + X.SR, 2), np.float32)
    put = lambda clip, at, pan=0.: X.place(tr, clip.astype(np.float32), max(0, at), pan)
    WH, WHD, POP, TICK, THUD, BOOM, DING, SWEEP, RISER = X.whoosh(.7, True, .32), X.whoosh(.6, False, .22), X.pop(.16), X.tick(.18), X.thud(.5, .45), X.boom(1.4, 70, 38, .55), X.ding(1320, .9, .14), X.sweep(.8, True, .12), X.riser(1.6, .16)
    for s in R.SC:
        v = s['v']; k = v['kind']; t0 = s['s0']
        if k == 'chapter':
            put(RISER, t0 - 1.5); put(WH, t0 - .15)
        elif k == 'number':
            if s['k'] == 0: put(BOOM, t0 + .05)
            elif v.get('hit') and not v.get('somber'): put(THUD, R.hit_t(s) - .02)
            else: put(WHD, t0 - .1)
        elif k == 'quote':
            put(TICK if v.get('fast') else POP, t0 + .02, -.2)
        elif k == 'chart':
            prev = R.SC[s['k'] - 1]['v'] if s['k'] else {}
            if not (prev.get('kind') == 'chart' and prev.get('series') == v['series']): put(SWEEP, t0 + .1)
            th = R.hit_t(s, .5)
            pend = min(max(th - .1, t0 + .8), s['s1'] - .3) if v.get('hit') else t0 + max(.9, (s['s1'] - t0) * .55)
            put(POP, pend, .2)
        elif k in ('files',) and v.get('stamp'):
            put(THUD, t0 + (s['s1'] - t0) * .55)
        elif k == 'doc':
            put(WHD, t0 - .05); put(THUD, R.hit_t(s, .6))
        elif k == 'map':
            put(WHD, t0 - .1)
            if v['state'] == 'closed': put(THUD, R.hit_t(s, .3))
            if v['state'] == 'attack':
                for j in range(3): put(X.boom(.9, 90, 45, .3), R.hit_t(s, .3) + .25 * j, (j - 1) * .4)
        elif k in ('event', 'headline', 'post', 'calendar', 'ships', 'duo', 'stack', 'versus', 'counts', 'lesson', 'events', 'dots'):
            prev = R.SC[s['k'] - 1]['v'] if s['k'] else {}
            if prev.get('kind') != k: put(WHD, t0 - .1)
            elif k in ('counts', 'lesson', 'versus'): put(POP, t0 + .1)
        elif k == 'bars':
            put(SWEEP, t0 + .2)
        elif k == 'coin':
            put(WH, t0); put(DING, t0 + 1.25)
        elif k == 'end':
            put(DING, R.wt(s, 'Follow', default=t0))
    X.write(out, tr); print('sfx', out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
