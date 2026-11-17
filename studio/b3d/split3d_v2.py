"""3D film v2 for the 2013 Bitcoin chain split - written shot by shot for a tall phone screen (owner Nov 17).

Rules (owner): every visual clear, nothing cut off, nothing on top of anything else, something new every 1-2 s.
 - Each shot is built at its own 'station' facing the camera, inside the safe middle of the frame
   (the top 22% belongs to the headline, the bottom 25% to the captions).
 - python split3d_v2.py <job> check          -> checks every frame (edges + overlaps), prints problems, renders nothing
 - python split3d_v2.py <job> <part> <nparts> [scale] [preview seconds...]

Free: Blender as a Python module (pip install bpy, Python 3.11), Cycles on the CPU.
"""
import bpy, json, math, os, random, sys
from mathutils import Vector

A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
JOB = A[0]
CHECK = len(A) > 1 and A[1] == 'check'
PART, NP = (0, 1) if CHECK else (int(A[1]), int(A[2]))
SCALE = float(A[3]) if len(A) > 3 and not CHECK else 1.0
PREVIEW = [float(x) for x in A[4:]] if not CHECK else []
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, '..', 'fonts', 'InterDisplay-Black.otf')
T = json.load(open(os.path.join(JOB, 'timing.json')))
PARA = T['para']; DUR = T['dur']
MISSING = []


def S(i): return PARA[i][0]
def E(i): return PARA[i][1]


def Wd(i, word, k=0):
    hits = [w[2] for w in T['words'] if w[0] == i and w[1] == word]
    if len(hits) <= k: MISSING.append((i, word)); return S(i) + .3
    return hits[k]


def F(t): return max(1, int(round(t * FPS)) + 1)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'BEZIER'
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, F(DUR)
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 10
sc.cycles.use_adaptive_sampling = True
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
sc.cycles.transparent_max_bounces = 8
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = int(540 * SCALE), int(960 * SCALE)
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.006, .008, .016, 1)


# ---------------------------------------------------------------- materials
def mat(name, base=(.03, .035, .05), metal=.7, rough=.32, emit=None, es=0.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = es
    if alpha < 1: b.inputs['Alpha'].default_value = alpha
    return m


def es_key(m, t, v):
    b = m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
    b.default_value = v; b.keyframe_insert('default_value', frame=F(t))


def col_key(m, t, c):
    b = m.node_tree.nodes['Principled BSDF'].inputs['Emission Color']
    b.default_value = (*c, 1); b.keyframe_insert('default_value', frame=F(t))


GOLD = (1.0, .2, .01); RED = (1.0, .04, .03); BLUE = (.02, .38, 1.0); WHITE = (1, 1, 1); GREEN = (.05, 1, .15)
M_BODY = mat('body')
M_GOLD = mat('wgold', emit=GOLD, es=3)
M_GRID = mat('grid', base=(0, 0, 0), emit=(.12, .2, .45), es=.45)
M_DUST = mat('dust', base=(0, 0, 0), emit=(.5, .6, 1), es=2)
M_COIN = mat('coin', base=(.9, .62, .15), metal=1, rough=.25, emit=GOLD, es=.6)
M_CASE = mat('case', base=(.08, .09, .12), metal=.6, rough=.35)


# ---------------------------------------------------------------- tracking what must stay clean
LABELS = []     # text objects: must be inside the safe area and never overlap each other or a PROP
PROPS = []      # main objects: must stay inside the safe area


def scale_keys(o, keys, base=1.0):
    for t, s in keys:
        o.scale = (base * s,) * 3 if s > 0 else (1e-4,) * 3
        o.keyframe_insert('scale', frame=F(t))


def pop(o, t_in, t_out=None, base=1.0, dur=.2):
    k = [(0, 0), (t_in - .01, 0), (t_in + dur, 1)]
    if t_out is not None: k += [(t_out - dur, 1), (t_out, 0)]
    scale_keys(o, k, base)


def cube(loc, size, wire, name='b', bevel=.07):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = (size,) * 3
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bv = o.modifiers.new('bv', 'BEVEL'); bv.width = bevel * size; bv.segments = 2
    wf = o.modifiers.new('wf', 'WIREFRAME'); wf.thickness = .05 * size; wf.use_replace = False; wf.material_offset = 1
    o.data.materials.append(M_BODY); o.data.materials.append(wire)
    return o


def text(body, loc, col, size=.6, es=None, check=True, parent=None):
    if es is None: es = 2.2 if col == WHITE else 3.2
    cu = bpy.data.curves.new('t', 'FONT'); cu.body = body
    try: cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    except Exception: pass
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.size = size; cu.extrude = .03
    o = bpy.data.objects.new('txt_' + body[:12], cu); sc.collection.objects.link(o)
    o.rotation_euler = (math.pi / 2, 0, 0)                                # stands up, faces the camera (-y)
    o.location = loc
    if parent: o.parent = parent
    m = mat('tm', base=(0, 0, 0), emit=col, es=es); o.data.materials.append(m)
    if check: LABELS.append(o)
    return o


def computer(loc, screen_col, name):
    """a monitor on a stand; returns (root, screen material)"""
    root = bpy.data.objects.new(name, None); sc.collection.objects.link(root); root.location = loc
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); case = bpy.context.object
    case.scale = (1.9, .18, 1.3); case.parent = root; case.data.materials.append(M_CASE)
    case.modifiers.new('bv', 'BEVEL').width = .05
    ms = mat('scr' + name, base=(0, 0, 0), emit=screen_col, es=1.6)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -.1, 0)); scr = bpy.context.object
    scr.scale = (1.7, 1.1, 1); scr.rotation_euler = (math.pi / 2, 0, 0); scr.parent = root; scr.data.materials.append(ms)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -.85)); st = bpy.context.object
    st.scale = (.18, .12, .45); st.parent = root; st.data.materials.append(M_CASE)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -1.08)); ft = bpy.context.object
    ft.scale = (.8, .4, .06); ft.parent = root; ft.data.materials.append(M_CASE)
    PROPS.append(case)
    return root, ms


def padlock(loc, m, s=1.0, parent=None):
    root = bpy.data.objects.new('lock', None); sc.collection.objects.link(root); root.location = loc
    if parent: root.parent = parent
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); b = bpy.context.object
    b.scale = (.7 * s, .25 * s, .55 * s); b.parent = root; b.data.materials.append(m)
    bpy.ops.mesh.primitive_torus_add(major_radius=.24 * s, minor_radius=.055 * s, location=(0, 0, .3 * s)); t_ = bpy.context.object
    t_.rotation_euler = (math.pi / 2, 0, 0); t_.parent = root; t_.data.materials.append(m)
    return root


# ---------------------------------------------------------------- camera: one station per shot, never still
bpy.ops.object.camera_add(location=(0, -12, 2)); CAM = bpy.context.object; sc.camera = CAM
CAM.data.lens = 32; CAM.data.clip_end = 400
tgt = bpy.data.objects.new('tgt', None); sc.collection.objects.link(tgt)
c = CAM.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
rig = bpy.data.objects.new('rig', None); sc.collection.objects.link(rig); CAM.parent = rig
CZ = .7                                                                   # height the camera looks at (centre of the safe area)


def cam(t, x, d=12.0, dz=1.6, look_z=CZ, dx=0.0):
    CAM.location = (x + dx, -d, look_z + dz); CAM.keyframe_insert('location', frame=F(t))
    tgt.location = (x, 0, look_z); tgt.keyframe_insert('location', frame=F(t))


def shot(t0, t1, x, d0=12.6, d1=11.6, dx0=-.5, dx1=.5):
    """a slow push-in with a little sideways slide: the picture never stops moving"""
    cam(t0, x, d0, dx=dx0); cam(t1, x, d1, dx=dx1)


CUTS = []


def cut(t, x_from, x_to, d=12):
    """whip to the next station in .3 s (the checker skips the whip itself)"""
    cam(t - .3, x_from, d); cam(t, x_to, d); CUTS.append(t)


# ---------------------------------------------------------------- world
bpy.ops.mesh.primitive_grid_add(x_subdivisions=260, y_subdivisions=60, size=1, location=(200, 20, -3.4))
g = bpy.context.object; g.scale = (520, 120, 1); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True); wf = g.modifiers.new('wf', 'WIREFRAME'); wf.thickness = .02; g.data.materials.append(M_GRID)
random.seed(7)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=.04, location=(0, 0, -50)); dust0 = bpy.context.object; dust0.data.materials.append(M_DUST)
for _ in range(500):
    d = dust0.copy(); sc.collection.objects.link(d)
    d.location = (random.uniform(-20, 460), random.uniform(6, 40), random.uniform(-3, 18))
bpy.ops.object.light_add(type='SUN', location=(0, -10, 20)); L1 = bpy.context.object; L1.data.energy = 2.5; L1.rotation_euler = (.7, 0, .3)

# ---------------------------------------------------------------- stations (x)
X_Y, X_PC, X_BLK, X_ACC, X_LCK, X_SHOP, X_PX, X_MIN, X_CLK, X_COIN = 0, 40, 80, 120, 160, 200, 240, 280, 320, 360
GAP, BS = .9, .72                                                         # chain block spacing / size

# ===== the Y: one gold trunk, a red (new v0.8) and a blue (old v0.7) branch that grow upward
for k, z in enumerate((-1.9, -1.0)):
    o = cube((X_Y, 0, z), BS, M_GOLD, name=f'trunk{k}'); PROPS.append(o)
fork = cube((X_Y, 0, -.1), BS, M_GOLD, name='fork'); PROPS.append(fork)
M_RED = mat('wred', emit=RED, es=3); M_BLUE = mat('wblue', emit=BLUE, es=2.8)
BX = {'r': X_Y - 1.5, 'b': X_Y + 1.5}; BASE = .95; SLOTS = 3                # 3 visible slots per branch (z .95 .. 2.75)
BR = {'r': [], 'b': []}


def branch_events(side):
    """[(t, count)] growth of each branch, keyed to the story"""
    t_split = Wd(0, 'split'); ev = []
    if side == 'r':
        ev += [(t_split + .15 * k, k) for k in range(1, 4)]                  # S0: both branches appear
        ev += [(S(6) + .15 + k * (E(6) - S(6) - .3) / 6, 3 + k) for k in range(1, 7)]   # S6: new chain runs ahead (to 9)
        ev += [(S(10) + .2 + k * .18, 9 + k) for k in range(1, 4)]          # S10: still growing a bit (to 12)
    else:
        ev += [(t_split + .15 * k, k) for k in range(1, 3)]
        ev += [(S(6) + .3 + k * (E(6) - S(6) - .4) / 3, 2 + k) for k in range(1, 4)]   # (to 5)
        ev += [(Wd(10, 'old') - .6 + k * (Wd(10, 'lead') - Wd(10, 'old') + .6) / 9, 5 + k) for k in range(1, 10)]   # overtakes (to 14)
    return ev


ARROWS = {}
for side, mm in (('r', M_RED), ('b', M_BLUE)):
    ev = branch_events(side); n_max = ev[-1][1]
    # diagonal link from the fork to each branch
    a = BX[side] - X_Y
    bpy.ops.mesh.primitive_cylinder_add(radius=.06, depth=math.hypot(a, BASE + .1) - .3, location=(X_Y + a / 2, 0, (BASE - .1) / 2), vertices=10)
    lk = bpy.context.object; lk.rotation_euler = (0, math.atan2(a, BASE + .1), 0); lk.data.materials.append(mm)
    pop(lk, ev[0][0] - .05, None, dur=.12)
    for j in range(1, n_max + 1):
        o = cube((BX[side], 0, -5), BS, mm, name=f'{side}{j}'); BR[side].append(o); PROPS.append(o)
        last_vis = False
        keys_s = [(0, 0)]
        for t, n in ev:
            first = max(1, n - SLOTS + 1)
            vis = first <= j <= n
            z = BASE + (j - first) * GAP if vis else (BASE - GAP if j < first else BASE + SLOTS * GAP)
            o.location = (BX[side], 0, z); o.keyframe_insert('location', frame=F(t + .12))
            if vis != last_vis:
                keys_s += [(t - .01, 0 if vis else 1), (t + .12, 1 if vis else 0)]
                last_vis = vis
        scale_keys(o, keys_s)

# S0 labels (the hook)
t_split = Wd(0, 'split')
l_one = text('1 BITCOIN', (X_Y, 0, 4.0), GOLD, 0.81); pop(l_one, .15, t_split - .05)
l_two = text('2 BITCOINS', (X_Y, 0, 4.0), WHITE, 0.81); pop(l_two, t_split, S(1) + .05)
# S1: a big red X stamps on the red (new) branch, it goes dark
t_kill = Wd(1, 'kill')
xx = bpy.data.objects.new('X', None); sc.collection.objects.link(xx); xx.location = (BX['r'], -.6, 1.5)
for ang in (.75, -.75):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); bar = bpy.context.object
    bar.scale = (.22, .1, 3.0); bar.rotation_euler = (0, ang, 0); bar.parent = xx
    bar.data.materials.append(mat('xm', base=(0, 0, 0), emit=RED, es=4))
pop(xx, t_kill, S(2) - .05, dur=.1)
l_kill = text('KILLED', (X_Y, 0, 4.0), RED, 1.04); pop(l_kill, t_kill, S(2) - .05)
es_key(M_RED, t_kill - .02, 3); es_key(M_RED, t_kill + .25, .35); es_key(M_RED, S(6) - .1, .35); es_key(M_RED, S(6) + .1, 3)

# ===== S2: the update - two computers, then a whole room of them
pc_new, ms_new = computer((X_PC - 1.6, 0, 1.4), RED, 'pcnew')
pc_old, ms_old = computer((X_PC + 1.6, 0, 1.4), BLUE, 'pcold')
for root, body, colr in ((pc_new, 'v0.8\nNEW', WHITE), (pc_old, 'v0.7\nOLD', WHITE)):
    tx = text(body, (0, -.16, 0), colr, .46, check=False, parent=root)
t_upd = Wd(2, 'update'); t_many = Wd(2, 'many')
pop(pc_new, Wd(2, 'version') - .1, t_many - .05); pop(pc_old, Wd(2, 'version') + .15, t_many - .05)
l_upd = text('THE UPDATE', (X_PC, 0, 4.0), WHITE, 0.81); pop(l_upd, S(2) + .05, t_many - .05)
random.seed(11)
room = []
for r_ in range(3):
    for k in range(4):
        newer = (r_, k) in ((0, 1), (1, 3), (2, 0))
        cm = mat('rc', base=(0, 0, 0), emit=RED if newer else BLUE, es=2.2)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(X_PC - 2.55 + k * 1.7, 0, 2.55 - r_ * 1.25))
        o = bpy.context.object; o.scale = (1.35, .12, .9); o.data.materials.append(cm)
        o.modifiers.new('bv', 'BEVEL').width = .04
        pop(o, t_many + .05 * (r_ * 4 + k), S(3) - .05, dur=.15); room.append(o); PROPS.append(o)
l_many = text('MOST STILL ON v0.7', (X_PC, 0, 4.0), BLUE, 0.65); pop(l_many, Wd(2, 'seven') - .3, S(3) - .05)

# ===== S3: one huge block falls in, full of transactions
t_huge = Wd(3, 'huge'); t_arr = Wd(3, 'arrived')
M_GLASS = mat('glass', base=(.1, .12, .2), metal=.2, rough=.15, alpha=.18)
M_HUGE = mat('whuge', emit=WHITE, es=3.5)
huge = bpy.data.objects.new('huge', None); sc.collection.objects.link(huge)
bpy.ops.mesh.primitive_cube_add(size=2.6, location=(0, 0, 0)); hg = bpy.context.object; hg.parent = huge; hg.data.materials.append(M_GLASS)
hg.modifiers.new('bv', 'BEVEL').width = .1
bpy.ops.mesh.primitive_cube_add(size=2.6, location=(0, 0, 0)); hw = bpy.context.object; hw.parent = huge
w2 = hw.modifiers.new('wf', 'WIREFRAME'); w2.thickness = .07; hw.data.materials.append(M_HUGE); PROPS.append(hw)
M_TX = mat('tx', base=(.2, .14, .03), emit=(1, .45, .05), es=2.2)
random.seed(3)
for _ in range(320):
    bpy.ops.mesh.primitive_cube_add(size=.12, location=(random.uniform(-1.1, 1.1), random.uniform(-1.1, 1.1), random.uniform(-1.1, 1.1)))
    q = bpy.context.object; q.parent = huge; q.data.materials.append(M_TX)
huge.location = (X_BLK, 40, 1.2); huge.keyframe_insert('location', frame=F(t_huge - .5))   # flies in from the deep, stays in the safe middle
huge.location = (X_BLK, 0, 1.2); huge.keyframe_insert('location', frame=F(t_arr + .05))
pop(huge, t_huge - .5, S(4) - .05, dur=.05)
es_key(M_HUGE, t_arr, 3.5); es_key(M_HUGE, t_arr + .08, 12); es_key(M_HUGE, t_arr + .5, 3.5)
l_huge = text('ONE HUGE BLOCK', (X_BLK, 0, 4.0), WHITE, 0.78); pop(l_huge, t_arr + .05, Wd(3, 'touched') - .05)
CNT = ['0', '1,000', '2,000', '3,000', '4,000', '5,000+']
t_c0, t_c1 = Wd(3, 'touched'), Wd(3, 'transactions') + .1
for k, v in enumerate(CNT):
    a_ = t_c0 + (t_c1 - t_c0) * k / len(CNT); b_ = t_c0 + (t_c1 - t_c0) * (k + 1) / len(CNT) if k < len(CNT) - 1 else S(4) - .05
    o = text(v, (X_BLK, 0, 3.8), GOLD, .85); pop(o, a_, b_, dur=.06)
l_txs = text('TRANSACTIONS', (X_BLK, 0, 3.05), WHITE, 0.49); pop(l_txs, t_c0, S(4) - .05)

# ===== S4: new computers accept it, old ones choke
pc_a, ms_a = computer((X_ACC - 1.6, 0, .9), RED, 'pca')
pc_b, ms_b = computer((X_ACC + 1.6, 0, .9), BLUE, 'pcb')
for root in (pc_a, pc_b): pop(root, S(4) - .05, S(5) - .05)
text('v0.8', (0, -.16, 0), WHITE, .42, check=False, parent=pc_a)
text('v0.7', (0, -.16, 0), WHITE, .42, check=False, parent=pc_b)
t_acc, t_chk = Wd(4, 'accepted'), Wd(4, 'choked')
mini = cube((X_ACC, 0, 6), .55, mat('wm', emit=WHITE, es=3), name='mini')
mini.keyframe_insert('location', frame=F(t_acc - .5)); mini.location = (X_ACC - 1.6, -.3, 1.0); mini.keyframe_insert('location', frame=F(t_acc))
mini.location = (X_ACC - 1.6, -.3, 3.0); mini.keyframe_insert('location', frame=F(t_acc + .35))
mini.keyframe_insert('location', frame=F(t_chk - .55)); mini.location = (X_ACC + 1.6, -.3, 1.0); mini.keyframe_insert('location', frame=F(t_chk - .05))
scale_keys(mini, [(0, 0), (t_acc - .51, 0), (t_acc - .4, 1), (t_acc, .7), (t_acc + .15, 1), (t_chk - .05, 1), (t_chk + .1, 0)])
col_key(ms_a, t_acc - .05, RED); col_key(ms_a, t_acc + .1, GREEN)
col_key(ms_b, t_chk - .05, BLUE); col_key(ms_b, t_chk + .08, RED)
l_ok = text('ACCEPTED', (X_ACC - 1.6, 0, -1.0), GREEN, 0.49); pop(l_ok, t_acc, S(5) - .05)
l_err = text('ERROR', (X_ACC + 1.6, 0, -1.0), RED, 0.59); pop(l_err, t_chk, S(5) - .05)
for k in range(8):                                                          # the old computer shakes
    pc_b.location = (X_ACC + 1.6 + (.12 if k % 2 else -.12), 0, .9); pc_b.keyframe_insert('location', frame=F(t_chk + k * .05))
pc_b.location = (X_ACC + 1.6, 0, .9); pc_b.keyframe_insert('location', frame=F(t_chk + .45))

# ===== S5: over 10,000 locks needed - the wall fills up red
t_lk = Wd(5, 'locks'); t_out = Wd(5, 'out')
wall = []
for r_ in range(4):
    for k in range(5):
        m = mat('lk', base=(.2, .22, .26), metal=.8, rough=.3, emit=WHITE, es=.4)
        o = padlock((X_LCK - 2.6 + k * 1.3, 0, 2.6 - r_ * 1.15), m, 1.0)
        pop(o, S(5) + .02 * (r_ * 5 + k), S(6) - .05, dur=.12)
        tt = Wd(5, 'needed') + (t_out - Wd(5, 'needed')) * (r_ * 5 + k) / 20
        col_key(m, tt - .05, WHITE); es_key(m, tt - .05, .4); col_key(m, tt + .05, RED); es_key(m, tt + .05, 3)
        wall.append(o)
        bpy.context.view_layer.update()
l_10k = text('10,000+ LOCKS NEEDED', (X_LCK, 0, 4.0), WHITE, 0.59); pop(l_10k, Wd(5, 'needed') - .4, t_out - .05)
l_out = text('OUT OF LOCKS', (X_LCK, 0, 4.0), RED, 0.81); pop(l_out, t_out, S(6) - .05)

# ===== S6 back on the Y: two Bitcoins at once
l_new = text('NEW', (BX['r'], 0, 4.0), RED, 0.65); pop(l_new, S(6) + .1, S(7) - .05)
l_old = text('OLD', (BX['b'], 0, 4.0), BLUE, 0.65); pop(l_old, S(6) + .1, S(7) - .05)

# ===== S7: Mt. Gox and BitPay shut deposits
t_shut = Wd(7, 'shut')
for k, (nm, xo) in enumerate((('MT. GOX', -1.65), ('BITPAY', 1.65))):
    root = bpy.data.objects.new('shop', None); sc.collection.objects.link(root); root.location = (X_SHOP + xo, 0, .9)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, .2, 0)); b_ = bpy.context.object; b_.scale = (2.8, .5, 3.0); b_.parent = root
    b_.data.materials.append(M_CASE); PROPS.append(b_)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -.08, -.35)); door = bpy.context.object
    door.scale = (2.2, 1.9, 1); door.rotation_euler = (math.pi / 2, 0, 0); door.parent = root
    door.data.materials.append(mat('door', base=(0, 0, 0), emit=(1, .85, .5), es=1.2))
    text(nm, (0, -.12, 1.05), WHITE, .5, check=False, parent=root)
    sh = bpy.data.objects.new('shut', None); sc.collection.objects.link(sh); sh.parent = root; sh.location = (0, -.16, 2.5)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); s_ = bpy.context.object; s_.scale = (2.3, .05, 2.0); s_.parent = sh
    s_.data.materials.append(mat('shm', base=(.25, .26, .3), metal=.9, rough=.4))
    text('PAUSED', (0, -.06, 0), RED, .52, check=False, parent=sh)
    sh.keyframe_insert('location', frame=F(t_shut + k * .15)); sh.location = (0, -.16, -.35); sh.keyframe_insert('location', frame=F(t_shut + .25 + k * .15))
    pop(root, S(7) + .05 + k * .2, S(8) - .05)
l_dep = text('DEPOSITS SHUT', (X_SHOP, 0, 4.0), RED, 0.72); pop(l_dep, Wd(7, 'deposits') - .1, S(8) - .05)

# ===== S8: the price falls off a cliff
pts = [(-3, -.2), (-2.4, .3), (-1.8, .0), (-1.2, .5), (-.6, .2), (0, .6), (.5, -.8), (1.0, -1.6), (1.5, -2.0), (2.1, -2.1), (2.8, -2.25)]
cu = bpy.data.curves.new('px', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = .08
sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
for k, (x, z) in enumerate(pts): sp.points[k].co = (x * .66, 0, z, 1)
px = bpy.data.objects.new('px', cu); sc.collection.objects.link(px); px.location = (X_PX, 0, 1.5)
px.data.materials.append(mat('pxm', base=(0, 0, 0), emit=RED, es=3.5)); PROPS.append(px)
cu.bevel_factor_end = 0; cu.keyframe_insert('bevel_factor_end', frame=F(S(8) + .05))
cu.bevel_factor_end = .55; cu.keyframe_insert('bevel_factor_end', frame=F(Wd(8, 'price')))
cu.bevel_factor_end = 1; cu.keyframe_insert('bevel_factor_end', frame=F(Wd(8, 'percent') + .1))
pop(px, S(8), S(9) - .05, dur=.05)
l_24 = text('-24%', (X_PX, 0, 3.8), RED, 1.1); pop(l_24, Wd(8, 'twentyfour'), S(9) - .05)

# ===== S9: miners switch back to the old version
t_ask = Wd(9, 'asked')
for k in range(5):
    m = mat('mn', base=(0, 0, 0), emit=RED, es=2.6)
    root = bpy.data.objects.new('miner', None); sc.collection.objects.link(root); root.location = (X_MIN - 2.5 + k * 1.25, 0, 1.0)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); b_ = bpy.context.object; b_.scale = (1.0, .9, 2.2); b_.parent = root
    b_.data.materials.append(M_CASE); PROPS.append(b_)
    for zz in (.55, -.35):
        bpy.ops.mesh.primitive_torus_add(major_radius=.3, minor_radius=.05, location=(0, -.47, zz)); fan = bpy.context.object
        fan.rotation_euler = (math.pi / 2, 0, 0); fan.parent = root; fan.data.materials.append(m)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -.46, -.95)); led = bpy.context.object; led.scale = (.8, .02, .1); led.parent = root
    led.data.materials.append(m)
    pop(root, S(9) + .04 * k, S(10) - .05, dur=.15)
    tt = Wd(9, 'back') - .2 + k * (E(9) - Wd(9, 'back')) / 5
    col_key(m, tt - .05, RED); col_key(m, tt + .1, BLUE)
    root.rotation_euler = (0, 0, 0); root.keyframe_insert('rotation_euler', frame=F(tt - .05))
    root.rotation_euler = (0, 0, math.pi * 2); root.keyframe_insert('rotation_euler', frame=F(tt + .35))
l_ask = text('DEVELOPERS ASK MINERS', (X_MIN, 0, 4.0), WHITE, 0.55); pop(l_ask, t_ask - .1, Wd(9, 'back') - .25)
l_sw = text('SWITCH BACK TO v0.7', (X_MIN, 0, 4.0), BLUE, 0.59); pop(l_sw, Wd(9, 'back') - .2, S(10) - .05)

# ===== S10: six hours on the clock, then the old chain wins
t_six = Wd(10, 'six'); t_old = Wd(10, 'old')
clk = bpy.data.objects.new('clock', None); sc.collection.objects.link(clk); clk.location = (X_CLK, 0, 1.2)
bpy.ops.mesh.primitive_torus_add(major_radius=2.0, minor_radius=.09, location=(0, 0, 0)); ring = bpy.context.object
ring.rotation_euler = (math.pi / 2, 0, 0); ring.parent = clk; ring.data.materials.append(mat('ck', base=(0, 0, 0), emit=WHITE, es=2.2)); PROPS.append(ring)
for k in range(12):
    a = k * math.pi / 6
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.65 * math.sin(a), 0, 1.65 * math.cos(a))); tk = bpy.context.object
    tk.scale = (.08, .05, .28 if k % 3 == 0 else .16); tk.rotation_euler = (0, a, 0); tk.parent = clk
    tk.data.materials.append(mat('tk', base=(0, 0, 0), emit=WHITE, es=1.6))
hand = bpy.data.objects.new('hand', None); sc.collection.objects.link(hand); hand.parent = clk; hand.location = (0, -.12, 0)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .65)); hd = bpy.context.object; hd.scale = (.12, .05, 1.3); hd.parent = hand
hd.data.materials.append(mat('hd', base=(0, 0, 0), emit=GOLD, es=3.2))
hand.rotation_euler = (0, 0, 0); hand.keyframe_insert('rotation_euler', frame=F(S(10)))
hand.rotation_euler = (0, math.pi, 0); hand.keyframe_insert('rotation_euler', frame=F(t_old - .3))   # 6 hours on a 12-hour dial = half a turn
pop(clk, S(10), t_old - .35, dur=.15)
l_6h = text('6 HOURS LATER', (X_CLK, 0, 4.0), WHITE, 0.75); pop(l_6h, t_six - .05, t_old - .35)
l_win = text('OLD CHAIN WINS', (X_Y, 0, 4.0), BLUE, 0.75); pop(l_win, Wd(10, 'won') - .1, S(11) - .05)

# ===== S11: the 24 blocks of the new chain fall away
t_wipe = Wd(11, 'wiped')
for k, o in enumerate(reversed(BR['r'])):
    t0 = Wd(11, 'twentyfour') + .1 + k * .06
    o.keyframe_insert('location', frame=F(t0)); x, y, z = o.location
    o.rotation_euler = (0, 0, 0); o.keyframe_insert('rotation_euler', frame=F(t0))
    o.location = (x - .3, y + 7, z - 1.2); o.keyframe_insert('location', frame=F(t0 + 1.0))   # tumbles away into the dark, not down over the captions
    o.rotation_euler = (random.uniform(-2, 2), random.uniform(-2, 2), 0); o.keyframe_insert('rotation_euler', frame=F(t0 + 1.0))
    scale_keys(o, [(t0 + .35, 1 if o.scale[0] > .5 else 1e-4), (t0 + .75, 0)])
l_24b = text('24 BLOCKS ERASED', (X_Y, 0, 4.0), RED, 0.68); pop(l_24b, Wd(11, 'twentyfour'), S(12) - .05)

# ===== S12: the same $10,000 spent twice
t_same, t_twice = Wd(12, 'same'), Wd(12, 'twice')
coins = []
for k in range(2):
    bpy.ops.mesh.primitive_cylinder_add(radius=.75, depth=.16, location=(X_COIN, 0, 1.9), vertices=48)
    o = bpy.context.object; o.rotation_euler = (math.pi / 2, 0, 0); o.data.materials.append(M_COIN); o.modifiers.new('bv', 'BEVEL').width = .04
    coins.append(o); PROPS.append(o)
    text('$', (0, 0, -.1), (1, .85, .3), .7, check=False, parent=o).rotation_euler = (0, 0, 0)
pop(coins[0], S(12) + .05, S(13) - .05); pop(coins[1], t_twice - .05, S(13) - .05, dur=.05)
for o, xo in ((coins[0], -1.6), (coins[1], 1.6)):
    o.location = (X_COIN, 0, 1.9); o.keyframe_insert('location', frame=F(t_twice))
    o.location = (X_COIN + xo, 0, .3); o.keyframe_insert('location', frame=F(t_twice + .5))
    o.rotation_euler = (math.pi / 2, 0, 0); o.keyframe_insert('rotation_euler', frame=F(S(12)))
    o.rotation_euler = (math.pi / 2, 0, math.pi * 2); o.keyframe_insert('rotation_euler', frame=F(t_twice + .5))
for nm, xo in (('OKPAY', -1.6), ('WALLET 2', 1.6)):
    o = text(nm, (X_COIN + xo, 0, -1.1), WHITE, .45); pop(o, t_twice + .3, S(13) - .05)
l_10k = text('$10,000', (X_COIN, 0, 3.85), GOLD, 0.8); pop(l_10k, Wd(12, 'ten') - .05, t_twice - .05)
l_x2 = text('$10,000 x2', (X_COIN, 0, 3.85), GOLD, 0.8); pop(l_x2, t_twice, S(13) - .05)

# ===== S13: back to one chain - loops to the start
l_bug = text('BUG?', (X_Y - 1.5, 0, 4.0), WHITE, 0.78); pop(l_bug, Wd(13, 'bug') - .05, DUR)
l_warn = text('WARNING?', (X_Y + 1.5, 0, 4.0), RED, 0.68); pop(l_warn, Wd(13, 'warning') - .05, DUR)
for o in BR['b']: pass                                                     # the old chain stays: it is today's Bitcoin

# ---------------------------------------------------------------- camera path (one station per shot)
shot(0, S(2) - .3, X_Y)
cut(S(2), X_Y, X_PC); shot(S(2), S(3) - .3, X_PC)
cut(S(3), X_PC, X_BLK); shot(S(3), S(4) - .3, X_BLK)
cut(S(4), X_BLK, X_ACC); shot(S(4), S(5) - .3, X_ACC)
cut(S(5), X_ACC, X_LCK); shot(S(5), S(6) - .3, X_LCK)
cut(S(6), X_LCK, X_Y); shot(S(6), S(7) - .3, X_Y)
cut(S(7), X_Y, X_SHOP); shot(S(7), S(8) - .3, X_SHOP)
cut(S(8), X_SHOP, X_PX); shot(S(8), S(9) - .3, X_PX)
cut(S(9), X_PX, X_MIN); shot(S(9), S(10) - .3, X_MIN)
cut(S(10), X_MIN, X_CLK); shot(S(10), t_old - .65, X_CLK)
cut(t_old - .35, X_CLK, X_Y); shot(t_old - .35, S(12) - .3, X_Y)
cut(S(12), X_Y, X_COIN); shot(S(12), S(13) - .3, X_COIN)
cut(S(13), X_COIN, X_Y); shot(S(13), DUR, X_Y, 12.0, 13.2, .4, -.3)

SHAKE = [(t_kill, .35), (t_arr, .5), (t_chk, .3), (Wd(8, 'dropped'), .3), (t_wipe, .35), (t_twice, .25)]
tt = 0.0
while tt <= DUR + .5:
    amp = .12 + sum(a * max(0, 1 - abs(tt - h) / .3) for h, a in SHAKE if tt >= h - .05)
    w = any(0 <= tt - h < .35 for h, _ in SHAKE)
    rig.location = (amp * math.sin(tt * 1.3 + (tt * 40 if w else 0)), 0, amp * .8 * math.sin(tt * 1.1 + 2 + (tt * 33 if w else 0)))
    rig.keyframe_insert('location', frame=F(tt)); tt += .1 if any(-.1 <= tt - h < .45 for h, _ in SHAKE) else .5

# ---------------------------------------------------------------- the checker: every frame clean
if MISSING: print('MISSING WORDS (check spelling):', sorted(set(MISSING)))


def bbox2d(o):
    from bpy_extras.object_utils import world_to_camera_view
    dg = bpy.context.evaluated_depsgraph_get(); oe = o.evaluated_get(dg)
    pts = [world_to_camera_view(sc, CAM, oe.matrix_world @ Vector(c)) for c in oe.bound_box]
    us = [p.x for p in pts]; vs = [p.y for p in pts]
    return min(us), max(us), min(vs), max(vs), min(p.z for p in pts)


def visible(o):
    m = o.matrix_world.to_scale()
    return min(abs(m.x), abs(m.y), abs(m.z)) > .4


if CHECK:
    SAFE = (.05, .95, .27, .77)                                              # u from left, v from bottom: headline above, captions below
    bad = []
    for f in range(1, F(DUR), 2):
        t = (f - 1) / FPS
        if any(c - .32 <= t <= c + .06 for c in CUTS): continue
        sc.frame_set(f)
        on = [(o, bbox2d(o)) for o in LABELS + PROPS if visible(o)]
        on = [(o, b) for o, b in on if b[4] > 0 and b[1] > 0 and b[0] < 1 and b[3] > .01 and b[2] < .99]   # in view
        for o, (u0, u1, v0, v1, _) in on:
            if u0 < SAFE[0] or u1 > SAFE[1] or v0 < SAFE[2] or v1 > SAFE[3]:
                bad.append((round(t, 2), 'EDGE', o.name, round(u0, 2), round(u1, 2), round(v0, 2), round(v1, 2)))
        labs = [(o, b) for o, b in on if o in LABELS]
        for k, (a, ba) in enumerate(labs):
            for o, bb in on:
                if o is a or (o in LABELS and on.index((o, bb)) < on.index((a, ba))): continue
                pad = .008
                if ba[0] < bb[1] - pad and bb[0] < ba[1] - pad and ba[2] < bb[3] - pad and bb[2] < ba[3] - pad:
                    bad.append((round(t, 2), 'OVERLAP', a.name, o.name))
    seen = set(); out = []
    for b in bad:
        key = b[1:3] + ((b[3],) if b[1] == 'OVERLAP' else ())
        if key in seen: continue
        seen.add(key); out.append(b)
    print('CHECK', 'OK' if not bad else f'{len(bad)} problem frames, {len(out)} distinct')
    for b in out[:80]: print(' ', b)
    sys.exit(0)

# ---------------------------------------------------------------- render this part
out = os.path.join(JOB, 'film'); os.makedirs(out, exist_ok=True)
if PREVIEW:
    for s_ in PREVIEW:
        sc.frame_set(F(s_)); sc.render.filepath = os.path.join(out, f'p_{s_:05.2f}.png')
        bpy.ops.render.render(write_still=True)
else:
    n = sc.frame_end; per = (n + NP - 1) // NP
    sc.frame_start = 1 + PART * per; sc.frame_end = min(n, (PART + 1) * per)
    sc.render.filepath = os.path.join(out, 'f_#####')
    bpy.ops.render.render(animation=True)
print('done part', PART, 'of', NP)
