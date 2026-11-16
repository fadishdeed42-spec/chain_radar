"""3D film for the 2013 Bitcoin chain split (Chain Secrets 3D pilot, owner Nov 16).

Free: Blender as a Python module (pip install bpy, Python 3.11), Cycles on the CPU.
Every move is keyed to the real spoken word times in the job's timing.json, so the picture stays locked to Liam.

usage: python split3d.py <jobdir> <part> <nparts> [scale] [frames...]
  renders the frames of one part into <jobdir>/film/ as f_00001.png ... (30 fps)
  'frames' (optional) renders only those seconds (preview), e.g. 2.1 5.4 13.7
"""
import bpy, json, math, os, random, sys

A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
JOB, PART, NP = A[0], int(A[1]), int(A[2])
SCALE = float(A[3]) if len(A) > 3 else 1.0
PREVIEW = [float(x) for x in A[4:]]
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, '..', 'fonts', 'InterDisplay-Black.otf')
T = json.load(open(os.path.join(JOB, 'timing.json')))
PARA = T['para']; DUR = T['dur']


def S(i): return PARA[i][0]                                             # scene start (s)


def Wd(i, word, k=0):
    """time of the k-th occurrence of a spoken word in scene i (falls back to the scene start)"""
    hits = [w[2] for w in T['words'] if w[0] == i and w[1] == word]
    return hits[k] if len(hits) > k else S(i)


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

world = bpy.data.worlds.new('w'); sc.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.006, .008, .016, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0


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


GOLD = (1.0, .62, .12); RED = (1.0, .16, .14); CYAN = (.15, .75, 1.0); WHITE = (1, 1, 1)
M_BODY = mat('body')
M_GOLD = mat('wgold', emit=GOLD, es=5)
M_RED = mat('wred', emit=RED, es=5)
M_CYAN = mat('wcyan', emit=CYAN, es=5)
M_HUGE = mat('whuge', emit=WHITE, es=4)
M_GLASS = mat('glass', base=(.1, .12, .2), metal=.2, rough=.15, alpha=.16)
M_TX = mat('tx', base=(.2, .14, .03), emit=GOLD, es=2.2)
M_GRID = mat('grid', base=(0, 0, 0), emit=(.12, .2, .45), es=.45)
M_DUST = mat('dust', base=(0, 0, 0), emit=(.5, .6, 1), es=2)
M_COIN = mat('coin', base=(.9, .62, .15), metal=1, rough=.25, emit=GOLD, es=.6)


# ---------------------------------------------------------------- helpers
def scale_keys(o, keys, base=1.0):
    """keys: [(t, s)] -> scale keyframes (s=0 hides). Holds flat between equal keys."""
    for t, s in keys:
        o.scale = (base * s,) * 3 if s > 0 else (1e-4,) * 3
        o.keyframe_insert('scale', frame=F(t))


def pop(o, t_in, t_out=None, base=1.0, dur=.22):
    k = [(0, 0), (t_in - .01, 0), (t_in + dur, 1)]
    if t_out is not None: k += [(t_out - dur, 1), (t_out, 0)]
    scale_keys(o, k, base)


def block(x, y, z, wire, size=1.0, name='b'):
    bpy.ops.mesh.primitive_cube_add(size=size, location=(x, y, z))
    o = bpy.context.object; o.name = name
    bv = o.modifiers.new('bv', 'BEVEL'); bv.width = .07 * size; bv.segments = 2
    wf = o.modifiers.new('wf', 'WIREFRAME'); wf.thickness = .045 * size; wf.use_replace = False; wf.material_offset = 1
    o.data.materials.append(M_BODY); o.data.materials.append(wire)
    return o


def link(a, b, wire):
    """a thin glowing bar between two block positions"""
    (x0, y0, z0), (x1, y1, z1) = a, b
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    bpy.ops.mesh.primitive_cylinder_add(radius=.07, depth=L, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), vertices=10)
    o = bpy.context.object
    o.rotation_euler = (0, math.pi / 2, math.atan2(dy, dx))
    o.data.materials.append(wire)
    return o


CAM = None


def text(body, loc, col, size=.8, es=6):
    cu = bpy.data.curves.new('t', 'FONT'); cu.body = body
    try: cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    except Exception: pass
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.size = size; cu.extrude = .04
    o = bpy.data.objects.new('txt', cu); sc.collection.objects.link(o)
    o.location = loc
    m = mat('tm', base=(0, 0, 0), emit=col, es=es); o.data.materials.append(m)
    c = o.constraints.new('TRACK_TO'); c.target = CAM; c.track_axis = 'TRACK_Z'; c.up_axis = 'UP_Y'
    return o


# ---------------------------------------------------------------- camera (keyed to the words)
bpy.ops.object.camera_add(location=(0, -10, 3)); CAM = bpy.context.object; sc.camera = CAM
CAM.data.lens = 26
CAM.data.clip_end = 400
tgt = bpy.data.objects.new('tgt', None); sc.collection.objects.link(tgt)
c = CAM.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'


def cam(t, loc, look):
    CAM.location = loc; CAM.keyframe_insert('location', frame=F(t))
    tgt.location = look; tgt.keyframe_insert('location', frame=F(t))


# ---------------------------------------------------------------- the world: grid floor + dust
bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=160, location=(20, 0, -4))
g = bpy.context.object; wf = g.modifiers.new('wf', 'WIREFRAME'); wf.thickness = .03; g.data.materials.append(M_GRID)
random.seed(7)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=.05, location=(0, 0, -50)); dust0 = bpy.context.object; dust0.data.materials.append(M_DUST)
for _ in range(160):
    d = dust0.copy(); sc.collection.objects.link(d)
    d.location = (random.uniform(-30, 60), random.uniform(-25, 25), random.uniform(-3, 16))
    s_ = random.uniform(.5, 1.8); d.scale = (s_,) * 3

bpy.ops.object.light_add(type='AREA', location=(10, -10, 14)); L1 = bpy.context.object; L1.data.energy = 3500; L1.data.size = 20
bpy.ops.object.light_add(type='AREA', location=(30, 12, 10)); L2 = bpy.context.object; L2.data.energy = 1500; L2.data.size = 20; L2.data.color = (.6, .7, 1)

# ---------------------------------------------------------------- the chain
GAP = 1.6
MAIN = [(k * GAP, 0, 0) for k in range(-13, 1)]                      # common chain, last block = 225,429 at x=0
for k, p in enumerate(MAIN):
    block(*p, M_GOLD, name=f'm{k}')
    if k: link(MAIN[k - 1], p, M_GOLD)

HX, HY = 2.5, .9                                                       # the huge block 225,430 (first block of the 0.8 chain)


def red_pos(j):   # j = 2..24
    return (HX + 1.45 + (j - 2) * GAP, 1.6, 0)


def cyan_pos(j):  # j = 1..26
    return (1.8 + (j - 1) * GAP, -2.0 if j > 1 else -1.5, 0)


# --- hook (S0): both branches grow fast, S1 the newer one dims ("kill"), S2 rewind: they shrink away
t_split, t_kill = Wd(0, 'split'), Wd(1, 'kill')
t_rw = S(2) + .05
HOOK = []
for j in range(1, 9):
    for side, pos, wire in (('r', red_pos(max(2, j + 1)) if j > 1 else (HX - .4, 1.4, 0), M_RED), ('c', cyan_pos(j), M_CYAN)):
        o = block(*pos, wire, name=f'h{side}{j}')
        t_in = t_split + .1 + j * .17
        t_out = t_rw + (8 - j) * .05 + .1
        pop(o, t_in, t_out, dur=.18)
        HOOK.append(o)
es_key(M_RED, S(0), 5); es_key(M_RED, t_kill - .05, 5); es_key(M_RED, t_kill + .3, .35); es_key(M_RED, t_rw + .4, .35); es_key(M_RED, t_rw + .6, 5)

# --- S3: the huge block falls and hits at "hit"
t_hit = Wd(3, 'hit')
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(HX, HY, 0)); huge = bpy.context.object
bv = huge.modifiers.new('bv', 'BEVEL'); bv.width = .1; bv.segments = 2
huge.data.materials.append(M_GLASS)
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(HX, HY, 0)); hw = bpy.context.object
w2 = hw.modifiers.new('wf', 'WIREFRAME'); w2.thickness = .06; hw.data.materials.append(M_HUGE); hw.parent = huge; hw.location = (0, 0, 0)
bpy.ops.mesh.primitive_cube_add(size=.11, location=(0, 0, -60)); tx0 = bpy.context.object; tx0.data.materials.append(M_TX)
random.seed(3)
for _ in range(260):                                                   # x-ray: the block is full of transactions
    q = tx0.copy(); sc.collection.objects.link(q); q.parent = huge
    q.location = (random.uniform(-.8, .8), random.uniform(-.8, .8), random.uniform(-.8, .8))
    q.rotation_euler = (random.random() * 3, random.random() * 3, random.random() * 3)
huge.location = (HX, HY, 14); huge.keyframe_insert('location', frame=1); huge.keyframe_insert('location', frame=F(t_hit - .55))
huge.location = (HX, HY, 0); huge.keyframe_insert('location', frame=F(t_hit))
pop(huge, t_hit - .56, None, dur=.05)
lk_h = link((0, 0, 0), (HX, HY, 0), M_HUGE); pop(lk_h, t_hit + .05, None, dur=.15)
es_key(M_HUGE, t_hit, 4); es_key(M_HUGE, t_hit + .08, 14); es_key(M_HUGE, t_hit + .5, 4)
t_acc = Wd(4, 'accepted')
M_HUGE.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1, 1, 1, 1)
M_HUGE.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].keyframe_insert('default_value', frame=F(t_acc - .05))
M_HUGE.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (*RED, 1)
M_HUGE.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].keyframe_insert('default_value', frame=F(t_acc + .2))
lbl_blk = text('BLOCK 225,430', (HX, HY, 2.5), GOLD, .62); pop(lbl_blk, Wd(3, 'block') - .1, S(4) + .3)

# --- versions (S2)
v7 = text('v0.7  OLD', (1.6, -2.4, 2.0), CYAN, .95); pop(v7, Wd(2, 'version'), S(3) + .2)
v8 = text('v0.8  NEW', (1.6, 2.4, 2.0), RED, .95); pop(v8, Wd(2, 'eight'), S(3) + .2)
ok = text('ACCEPTED', (HX + .5, HY + 2.6, 1.6), RED, .5); pop(ok, t_acc, S(5) + .1)
no = text("CAN'T READ IT", (1.8, -3.6, 1.2), CYAN, .5); pop(no, Wd(4, 'couldnt'), S(5) + .1)

# --- the two real chains: red (0.8) 2..24, cyan (0.7) 1..26, growing on the story's words
t_c1 = Wd(4, 'couldnt')
t_sp = Wd(5, 'split')
REDB, CYB = {}, {}


def grow_times(n0, n1, t0, t1):
    return {j: t0 + (t1 - t0) * (k + 1) / max(1, (n1 - n0)) for k, j in enumerate(range(n0 + 1, n1 + 1))}


R_T = {}; C_T = {1: t_c1}
R_T.update(grow_times(1, 9, t_sp, S(7)))                               # split: the 0.8 chain (more miners) runs ahead
C_T.update(grow_times(1, 6, t_sp + .2, S(7)))
R_T.update(grow_times(9, 14, S(8), S(9)))                              # developers pick 0.7, pools downgrade: 0.7 speeds up
C_T.update(grow_times(6, 20, Wd(8, 'picked'), S(9)))
R_T.update(grow_times(14, 24, S(9), Wd(9, 'joined')))
C_T.update(grow_times(20, 26, S(9), Wd(9, 'joined') + .2))
t_wipe = Wd(10, 'twentyfour')
for j in range(2, 25):
    o = block(*red_pos(j), M_RED, name=f'r{j}'); pop(o, R_T[j], None, dur=.2); REDB[j] = o
    prev = red_pos(j - 1) if j > 2 else (HX, HY, 0)
    lk = link(prev, red_pos(j), M_RED); pop(lk, R_T[j] + .05, None, dur=.15); REDB[f'l{j}'] = lk
for j in range(1, 27):
    o = block(*cyan_pos(j), M_CYAN, name=f'c{j}'); pop(o, C_T[j], None, dur=.2); CYB[j] = o
    lk = link(cyan_pos(j - 1) if j > 1 else (0, 0, 0), cyan_pos(j), M_CYAN); pop(lk, C_T[j] + .05, None, dur=.15)

# --- S5: the lock that ran out
lock = bpy.data.objects.new('lock', None); sc.collection.objects.link(lock); lock.location = (1.2, -3.4, 1.7)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); lb = bpy.context.object; lb.scale = (.9, .35, .7); lb.parent = lock
lb.modifiers.new('bv', 'BEVEL').width = .08
M_LOCK = mat('lock', base=(.25, .27, .32), metal=.9, rough=.3, emit=RED, es=0)
lb.data.materials.append(M_LOCK)
bpy.ops.mesh.primitive_torus_add(major_radius=.32, minor_radius=.07, location=(0, 0, .45)); ls = bpy.context.object
ls.rotation_euler = (math.pi / 2, 0, 0); ls.parent = lock; ls.data.materials.append(M_LOCK)
pop(lock, Wd(5, 'database'), t_sp - .1)
es_key(M_LOCK, Wd(5, 'locks') - .05, 0); es_key(M_LOCK, Wd(5, 'locks') + .15, 6)
lt = text('OUT OF LOCKS', (1.4, -3.4, 3.1), RED, .55); pop(lt, Wd(5, 'locks'), t_sp - .1)

# --- S6: exchanges pause
gx = text('MT. GOX', (5.5, -.2, 3.2), WHITE, 1.1); pop(gx, Wd(6, 'gox') - .1, S(7) - .05)
bp = text('BITPAY', (11.0, -.2, 3.2), WHITE, 1.1); pop(bp, Wd(6, 'bitpay') - .1, S(7) - .05)
for x in (5.5, 11.0):
    pz = bpy.data.objects.new('pz', None); sc.collection.objects.link(pz); pz.location = (x, -.2, 4.9)
    for dx in (-.22, .22):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(dx, 0, 0)); b_ = bpy.context.object; b_.scale = (.16, .16, .7); b_.parent = pz
        b_.data.materials.append(mat('pz', base=(0, 0, 0), emit=RED, es=6))
    pop(pz, Wd(6, 'paused'), S(7) - .05)

# --- S7: the price drops 24%
pts = [(0, 0), (1, .25), (2, -.1), (3, .2), (4, -.2), (5, -.9), (6, -1.6), (7, -2.2), (8, -2.6)]
cu = bpy.data.curves.new('px', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = .09
sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
for k, (x, y) in enumerate(pts): sp.points[k].co = (x * 1.3, 0, y * 1.1, 1)
px = bpy.data.objects.new('px', cu); sc.collection.objects.link(px); px.location = (6, 5, 6.2)
px.data.materials.append(mat('pxm', base=(0, 0, 0), emit=RED, es=7))
cu.bevel_factor_end = 0; cu.keyframe_insert('bevel_factor_end', frame=F(Wd(7, 'price')))
cu.bevel_factor_end = 1; cu.keyframe_insert('bevel_factor_end', frame=F(Wd(7, 'percent') + .2))
pop(px, Wd(7, 'price') - .05, S(8) + .1, dur=.05)
p24 = text('-24%', (16.8, 5, 3.0), RED, 1.3, es=8); pop(p24, Wd(7, 'twentyfour'), S(8) + .1)

# --- S8/S9: the old chain wins
win = text('v0.7 WINS', (24, -2.0, 4.0), CYAN, 2.4, es=8); pop(win, Wd(9, 'joined'), S(10) + .3)

# --- S10: the 24 blocks of the 0.8 chain fall into the dark
for k, j in enumerate(range(24, 1, -1)):
    o = REDB[j]; t0 = t_wipe + .25 + k * .05
    o.keyframe_insert('location', frame=F(t0))
    o.rotation_euler = (0, 0, 0); o.keyframe_insert('rotation_euler', frame=F(t0))
    x, y, z = o.location; o.location = (x, y + 1.5, z - 14); o.keyframe_insert('location', frame=F(t0 + 1.4))
    o.rotation_euler = (random.uniform(-2, 2), random.uniform(-2, 2), 0); o.keyframe_insert('rotation_euler', frame=F(t0 + 1.4))
    scale_keys(o, [(t0 + .9, 1), (t0 + 1.5, 0)])
    lk = REDB[f'l{j}']; scale_keys(lk, [(t0 - .02, 1), (t0 + .1, 0)])
for o in (huge, lk_h):                                                 # 225,430 itself was orphaned too
    t0 = t_wipe + .25 + 23 * .05
    o.keyframe_insert('location', frame=F(t0)); x, y, z = o.location
    o.location = (x, y + 1.5, z - 14); o.keyframe_insert('location', frame=F(t0 + 1.4))
    scale_keys(o, [(t0 + .9, 1), (t0 + 1.5, 0)])
gone = text('24 BLOCKS ERASED', (20, 3.0, 4.0), RED, 2.2, es=8); pop(gone, t_wipe, S(11) - .05)

# --- S11: the double spend (one coin, paid twice)
cend = cyan_pos(26)
coin = []
for k in range(2):
    bpy.ops.mesh.primitive_cylinder_add(radius=.75, depth=.16, location=(cend[0] + 2.2, -2.0, 2.0), vertices=48)
    o = bpy.context.object; o.rotation_euler = (math.pi / 2, 0, 0); o.data.materials.append(M_COIN)
    o.modifiers.new('bv', 'BEVEL').width = .04
    coin.append(o)
t_dbl = Wd(11, 'double')
pop(coin[0], Wd(11, 'someone'), S(12) - .05); pop(coin[1], t_dbl, S(12) - .05, dur=.05)
coin[1].location = (cend[0] + 2.2, -2.0, 2.0); coin[1].keyframe_insert('location', frame=F(t_dbl))
coin[1].location = (cend[0] + 2.2, 1.6, 2.0); coin[1].keyframe_insert('location', frame=F(t_dbl + .6))
coin[0].location = (cend[0] + 2.2, -2.0, 2.0); coin[0].keyframe_insert('location', frame=F(t_dbl))
coin[0].location = (cend[0] + 2.2, -3.4, 2.0); coin[0].keyframe_insert('location', frame=F(t_dbl + .6))
for o in coin:
    o.rotation_euler = (math.pi / 2, 0, 0); o.keyframe_insert('rotation_euler', frame=F(Wd(11, 'someone')))
    o.rotation_euler = (math.pi / 2, 0, math.pi * 2); o.keyframe_insert('rotation_euler', frame=F(S(12)))
usd = text('$10,000', (cend[0] + 2.2, -.9, 3.6), GOLD, .8, es=8); pop(usd, Wd(11, 'ten'), S(12) - .05)
two = text('PAID TWICE', (cend[0] + 2.2, -.9, .3), WHITE, .5); pop(two, Wd(11, 'spent'), S(12) - .05)

# ---------------------------------------------------------------- camera path
cam(0, (-24, -5.5, 1.8), (-14, 0, 0))
cam(t_split, (-5, -6.5, 3.2), (2, 0, 0))
cam(S(1), (3, -11, 9), (7, 0, 0))
cam(t_kill + .2, (7, -4, 15), (8, .5, 0))
cam(S(2) - .1, (7, -4.5, 14.5), (8, .5, 0))
cam(S(2) + .9, (-4.5, -10.5, 3.6), (1.2, 0, 1.0))
cam(S(3) - .4, (-3.5, -10, 3.2), (1.4, 0, 1.0))
cam(S(3) - .1, (-2, -6.8, 2.2), (1.6, 0, 1.0))
cam(t_hit - .2, (-2.5, -8.5, 4.2), (2.4, .6, 1.2))
cam(t_hit + .05, (-2.2, -8.1, 3.8), (2.5, .7, .6))
cam(S(4) - .1, (5.5, -6.5, 3.2), (2.6, .6, .6))
cam(S(5) - .1, (6.5, -7.5, 4.2), (3, 0, .5))
cam(Wd(5, 'database'), (.2, -10.5, 3.2), (1.3, -2.2, 1.7))
cam(t_sp - .2, (.6, -10, 3.0), (1.4, -2.2, 1.6))
cam(t_sp + .7, (4, -13, 7), (6, 0, 0))
cam(S(6) + .3, (8.2, -16, 8), (8.2, 0, 2))
cam(S(7) - .1, (10, -15, 7), (10, 0, 0))
cam(S(8) - .1, (12, -14, 7), (12, 2, 2.5))
cam(S(8) + 1.4, (11, -12, 5), (15, -1, 0))
cam(S(9) - .1, (26, -12, 5), (31, -1, 0))
cam(Wd(9, 'joined'), (22, -27, 16), (21, 0, 1))
cam(S(10) + .2, (22, -26, 15), (21, 0, 1))
cam(S(11) - .1, (20, -24, 9), (20, 0, -2))
cam(S(11) + .6, (cend[0] - 1, -8.5, 3.4), (cend[0] + 2, -1.2, 1.8))
cam(S(12) - .1, (cend[0] + 1, -8, 3.2), (cend[0] + 2.2, -1.2, 1.8))
cam(DUR, (cend[0] - 26, -13, 5), (cend[0] - 12, -2, 0))

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
