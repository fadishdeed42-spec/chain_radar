"""3D film: Trump meme coin (owner Nov 19 style test D). Same rules + checker as split3d_v2.py."""
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
CZ = 1.35                                                                   # height the camera looks at (centre of the safe area)


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

# ---------------------------------------------------------------- stations (x): Trump coin story (owner Nov 19)
X_LAUNCH, X_CHART, X_PIE, X_CRASH, X_DIN, X_JUMP = 0, 9, 18, 27, 36, 45
# real TRUMPUSDT daily closes (Binance), Jan 19 -> Mar 11 2025, and Apr 20 -> Apr 26 2025
DOWN = [46.5, 36.5, 43.76, 36.86, 34.69, 30.18, 28.89, 27.38, 28.0, 27.34, 27.25, 26.06, 24.14, 19.7, 21.01, 19.66, 17.19, 18.17, 17.08, 16.57, 17.25, 15.88, 15.91, 15.35, 15.45, 16.3, 21.58, 18.66, 18.75, 17.18, 16.38, 17.03, 17.09, 15.9, 16.52, 16.13, 12.95, 13.25, 13.3, 12.59, 12.95, 13.17, 16.96, 12.83, 12.97, 13.22, 13.08, 12.36, 12.02, 10.71, 10.3, 10.5]
UP = [8.18, 8.31, 9.23, 13.29, 12.21, 13.34, 15.61]
M_COINF = mat('coinface', base=(1, .72, .2), metal=1, rough=.22, emit=GOLD, es=.8)
M_GREEN = mat('wgreen', emit=GREEN, es=3)


def coin(loc, r=1.5, name='coin'):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=.28 * r, location=loc, vertices=64)
    o = bpy.context.object; o.name = name; o.rotation_euler = (math.pi / 2, 0, 0); o.data.materials.append(M_COINF)
    o.modifiers.new('bv', 'BEVEL').width = .05 * r
    bpy.ops.mesh.primitive_torus_add(major_radius=r * .82, minor_radius=r * .035, location=(0, 0, .15 * r)); ring = bpy.context.object
    ring.parent = o; ring.data.materials.append(M_GOLD)
    t_ = text('TRUMP', (0, 0, .15 * r + .01), (1, .95, .7), .36 * r, es=1.5, check=False, parent=o); t_.rotation_euler = (0, 0, 0)
    PROPS.append(o)
    return o


def line_chart(vals, loc, w, h, col, name):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = .07
    sp = cu.splines.new('POLY'); sp.points.add(len(vals) - 1)
    lo, hi = min(vals), max(vals)
    for k, v in enumerate(vals): sp.points[k].co = (-w / 2 + w * k / (len(vals) - 1), 0, -h / 2 + h * (v - lo) / (hi - lo), 1)
    o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o); o.location = loc
    o.data.materials.append(mat(name + 'm', base=(0, 0, 0), emit=col, es=3.5))
    return o, cu


def arc(loc, r, frac0, frac1, col, name, depth=.55):
    """a thick ring segment from frac0 to frac1 of a full turn (a pie chart slice), facing the camera"""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = depth; cu.bevel_resolution = 2
    sp = cu.splines.new('POLY'); n = 64; sp.points.add(n)
    for k in range(n + 1):
        a = math.pi / 2 - 2 * math.pi * (frac0 + (frac1 - frac0) * k / n)
        sp.points[k].co = (r * math.cos(a), 0, r * math.sin(a), 1)
    o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o); o.location = loc
    o.data.materials.append(mat(name + 'm', base=(0, 0, 0), emit=col, es=3))
    return o, cu


# ===== S0: a coin launches - three days before taking office
t_launch = Wd(0, 'launched')
c0 = coin((X_LAUNCH, 0, .6), 1.3, 'c0')
c0.keyframe_insert('location', frame=F(t_launch - .7)); c0.location = (X_LAUNCH, 0, 1.2); c0.keyframe_insert('location', frame=F(t_launch + .1))
c0.rotation_euler = (math.pi / 2, 0, 0); c0.keyframe_insert('rotation_euler', frame=F(t_launch - .7))
c0.rotation_euler = (math.pi / 2, 0, math.pi * 4); c0.keyframe_insert('rotation_euler', frame=F(t_launch + .5))
c0.rotation_euler = (math.pi / 2, 0, math.pi * 4 + .5); c0.keyframe_insert('rotation_euler', frame=F(S(1)))
scale_keys(c0, [(0, 0), (t_launch - .71, 0), (t_launch - .6, 1), (S(1) + .12, 1), (S(1) + .2, 0)])
l_3d = text('3 DAYS BEFORE', (X_LAUNCH, 0, 3.75), WHITE, .62); pop(l_3d, .1, t_launch - .1)
l_3d2 = text('TAKING OFFICE', (X_LAUNCH, 0, 3.0), GOLD, .5); pop(l_3d2, Wd(0, 'office') - .1, t_launch - .1)
l_new = text('JAN 17, 2025', (X_LAUNCH, 0, 3.75), GOLD, .62); pop(l_new, t_launch, S(1) + .12)
l_new2 = text('A NEW CRYPTO COIN', (X_LAUNCH, 0, -.95), WHITE, .48); pop(l_new2, Wd(0, 'crypto') - .1, S(1) + .12)

# ===== S1: two days later - $73, $14.5 billion
up_vals = [3, 9, 18, 27.25, 46.5, 73]                                       # launch day climb, then the $73 top (Jan 19)
ch1, cu1 = line_chart(up_vals, (X_CHART, 0, 1.0), 4.0, 3.0, GREEN, 'up')
cu1.bevel_factor_end = 0; cu1.keyframe_insert('bevel_factor_end', frame=F(S(1)))
cu1.bevel_factor_end = 1; cu1.keyframe_insert('bevel_factor_end', frame=F(Wd(1, 'seventythree') + .2))
pop(ch1, S(1) - .3, S(2) + .12, dur=.05)
c1 = coin((X_CHART + 2.0, -.3, 2.5), .45, 'c1'); PROPS.remove(c1); pop(c1, Wd(1, 'seventythree') - .1, S(2) + .12)
l_73 = text('$73', (X_CHART - 1.4, 0, 3.6), GREEN, 1.0); pop(l_73, Wd(1, 'seventythree') - .05, Wd(1, 'fourteen') - .1)
l_145 = text('$14.5 BILLION', (X_CHART - .4, 0, 3.6), GOLD, .7); pop(l_145, Wd(1, 'fourteen') - .05, S(2) + .12)
l_2d = text('2 DAYS LATER', (X_CHART, 0, -.95), WHITE, .48); pop(l_2d, S(1), S(2) + .12)

# ===== S2: 80% belongs to Trump-linked companies
p80, pc80 = arc((X_PIE, 0, 1.0), 1.55, 0, .8, GOLD, 'p80', .42)
p20, pc20 = arc((X_PIE, 0, 1.0), 1.55, .805, .995, WHITE, 'p20', .42)
for cu_, a_, b_ in ((pc80, Wd(2, 'eighty') - .1, Wd(2, 'percent') + .4), (pc20, Wd(2, 'percent') + .3, Wd(2, 'coins') + .3)):
    cu_.bevel_factor_end = 0; cu_.keyframe_insert('bevel_factor_end', frame=F(a_))
    cu_.bevel_factor_end = 1; cu_.keyframe_insert('bevel_factor_end', frame=F(b_))
pop(p80, S(2) - .3, S(3) + .12, dur=.05); pop(p20, S(2) - .3, S(3) + .12, dur=.05)
l_80 = text('80%', (X_PIE, 0, 1.0), GOLD, .9); LABELS.remove(l_80); pop(l_80, Wd(2, 'eighty'), S(3) + .12)
l_tl = text('TRUMP-LINKED COMPANIES', (X_PIE, 0, 3.75), GOLD, .4); pop(l_tl, Wd(2, 'trumplinked') - .1, S(3) + .12)
l_ev = text('20% EVERYONE ELSE', (X_PIE, 0, -1.1), WHITE, .42); pop(l_ev, Wd(2, 'coins'), S(3) + .12)

# ===== S3: by March, down more than 80%
ch3, cu3 = line_chart(DOWN, (X_CRASH, 0, 1.0), 4.2, 3.0, RED, 'down')
cu3.bevel_factor_end = 0; cu3.keyframe_insert('bevel_factor_end', frame=F(S(3)))
cu3.bevel_factor_end = 1; cu3.keyframe_insert('bevel_factor_end', frame=F(Wd(3, 'down') + .5))
pop(ch3, S(3) - .3, S(4) + .12, dur=.05)
l_mar = text('JAN → MARCH 2025', (X_CRASH, 0, -.95), WHITE, .44); pop(l_mar, S(3), S(4) + .12)
l_m80 = text('-80%+', (X_CRASH + .8, 0, 3.7), RED, 1.0); pop(l_m80, Wd(3, 'eighty') - .1, S(4) + .12)

# ===== S4: dinner with the President for the top 220 holders
tab = bpy.data.objects.new('table', None); sc.collection.objects.link(tab); tab.location = (X_DIN, 0, .3)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); top = bpy.context.object; top.scale = (5.6, 2.2, .14); top.parent = tab
top.data.materials.append(mat('cloth', base=(.85, .85, .9), metal=0, rough=.6, emit=WHITE, es=.25)); PROPS.append(top)
for xx in (-2.5, 2.5):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(xx, 0, -.75)); lg = bpy.context.object; lg.scale = (.12, 1.8, 1.4); lg.parent = tab; lg.data.materials.append(M_CASE)
M_PLATE = mat('plate', base=(.9, .9, .9), metal=0, rough=.3, emit=WHITE, es=.6)
for k in range(5):
    bpy.ops.mesh.primitive_cylinder_add(radius=.38, depth=.04, location=(-2.0 + k, -.5, .1)); pl = bpy.context.object; pl.parent = tab; pl.data.materials.append(M_PLATE)
for xx in (-1.6, 1.6):
    bpy.ops.mesh.primitive_cylinder_add(radius=.06, depth=.7, location=(xx, .4, .45)); cd = bpy.context.object; cd.parent = tab; cd.data.materials.append(M_PLATE)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=.1, location=(xx, .4, .88)); fl = bpy.context.object; fl.parent = tab; fl.data.materials.append(mat('fl', base=(0, 0, 0), emit=(1, .55, .1), es=8))
pop(tab, S(4) - .3, S(5) + .12)
l_220 = text('TOP 220 HOLDERS', (X_DIN, 0, 3.0), GOLD, .62); pop(l_220, Wd(4, 'top') - .1, S(5) + .12)
l_din = text('DINNER WITH THE PRESIDENT', (X_DIN, 0, 3.75), WHITE, .44); pop(l_din, Wd(4, 'dinner') - .1, S(5) + .12)

# ===== S5: the price jumps again
ch5, cu5 = line_chart(UP, (X_JUMP, 0, 1.0), 4.0, 2.8, GREEN, 'jump')
cu5.bevel_factor_end = 0; cu5.keyframe_insert('bevel_factor_end', frame=F(S(5)))
cu5.bevel_factor_end = 1; cu5.keyframe_insert('bevel_factor_end', frame=F(E(5) + .2))
pop(ch5, S(5) - .3, S(6) + .12, dur=.05)
l_ag = text('APRIL 2025: JUMPS AGAIN', (X_JUMP, 0, 3.9), GREEN, .46); pop(l_ag, Wd(5, 'jumps') - .1, S(6) + .12)

# ===== S6: meme coin, or dinner ticket? (back at the coin: loops to the start)
c6 = coin((X_LAUNCH - 1.25, 0, 1.2), .95, 'c6'); pop(c6, S(6) - .3, DUR)
tk = bpy.data.objects.new('ticket', None); sc.collection.objects.link(tk); tk.location = (X_LAUNCH + 1.3, 0, 1.2)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0)); tb = bpy.context.object; tb.scale = (1.7, .06, 1.05); tb.parent = tk
tb.data.materials.append(mat('tkm', base=(.12, .1, .05), metal=.6, rough=.3, emit=GOLD, es=.5)); PROPS.append(tb)
text('DINNER', (0, -.08, .18), (1, .85, .4), .34, check=False, parent=tk); text('TICKET', (0, -.08, -.2), (1, .85, .4), .3, check=False, parent=tk)
pop(tk, Wd(6, 'dinner') - .2, DUR)
l_mc = text('MEME COIN?', (X_LAUNCH - 1.25, 0, 2.9), GOLD, .42); pop(l_mc, Wd(6, 'meme') - .1, DUR)
l_dt = text('DINNER TICKET?', (X_LAUNCH + 1.3, 0, 2.6), WHITE, .34); pop(l_dt, Wd(6, 'dinner') - .1, DUR)

# ---------------------------------------------------------------- camera path
shot(0, S(1) - .3, X_LAUNCH, 9.4, 8.7)
cut(S(1), X_LAUNCH, X_CHART, 9.4); shot(S(1), S(2) - .3, X_CHART, 9.4, 8.7)
cut(S(2), X_CHART, X_PIE, 9.4); shot(S(2), S(3) - .3, X_PIE, 9.4, 8.7)
cut(S(3), X_PIE, X_CRASH, 9.4); shot(S(3), S(4) - .3, X_CRASH, 9.4, 8.7)
cut(S(4), X_CRASH, X_DIN, 9.4); shot(S(4), S(5) - .3, X_DIN, 9.4, 8.7)
cut(S(5), X_DIN, X_JUMP, 9.4); shot(S(5), S(6) - .3, X_JUMP, 9.4, 8.7)
cut(S(6), X_JUMP, X_LAUNCH, 9.4); shot(S(6), DUR, X_LAUNCH, 8.8, 9.8, .4, -.3)

SHAKE = [(t_launch, .35), (Wd(1, 'seventythree'), .25), (Wd(3, 'down'), .35), (Wd(5, 'jumps'), .3)]
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
