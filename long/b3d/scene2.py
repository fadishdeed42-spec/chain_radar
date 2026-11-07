"""Binance $6.3B hack — 3D, one continuous camera move, every action keyed to the word that says it (beats.json).
blender -b -P scene2.py -- DUR START END OUTDIR [mid]"""
import bpy, sys, math, json, os
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
DUR, START, END, OUT = float(argv[0]), int(argv[1]), int(argv[2]), argv[3]
MID = len(argv) > 4 and argv[4] == 'mid'
FPS = 30; NF = int(DUR * FPS)
B = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'beats.json')))   # word -> seconds (video time)
F = lambda s: max(1, int(round(s * FPS)) + 1)
def bt(k): return B[k]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 14 if MID else 32; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4; sc.cycles.transmission_bounces = 4; sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = (540, 960) if MID else (720, 1280)
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, NF
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.image_settings.file_format = 'PNG'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def mat(name, color, metal=0., rough=.5, emit=None, strength=0., alpha=1., trans=0.):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    b.inputs['Alpha'].default_value = alpha; b.inputs['Transmission Weight'].default_value = trans
    if emit: b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = strength
    return m
def put(o, m):
    o.data.materials.append(m); return o
def cube(loc, scale, m):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.scale = scale; return put(o, m)
def text(body, loc, size, m, rot=(math.radians(90), 0, math.pi), align='CENTER'):   # faces +Y, where the camera is
    bpy.ops.object.text_add(location=loc, rotation=rot); t = bpy.context.object
    t.data.body = body; t.data.align_x = align; t.data.align_y = 'CENTER'; t.data.size = size; t.data.extrude = .02
    try: t.data.font = bpy.data.fonts.load(FONT)
    except Exception: pass
    return put(t, m)
def kf(o, path, t, v):
    setattr(o, path, v); o.keyframe_insert(data_path=path, frame=F(t))
def appear(o, t, dur=.35, base=None):
    s = tuple(base or o.scale); kf(o, 'scale', 0, (0, 0, 0)); kf(o, 'scale', max(0, t - .01), (0, 0, 0)); kf(o, 'scale', t + dur, s)
def vanish(o, t, dur=.3):
    s = tuple(o.scale); kf(o, 'scale', t, s); kf(o, 'scale', t + dur, (0, 0, 0))
def emit_to(m, t, color, strength, dur=.4):
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Emission Strength'].keyframe_insert('default_value', frame=F(t))
    b.inputs['Emission Color'].keyframe_insert('default_value', frame=F(t))
    b.inputs['Emission Color'].default_value = (*color, 1); b.inputs['Emission Strength'].default_value = strength
    b.inputs['Emission Strength'].keyframe_insert('default_value', frame=F(t + dur)); b.inputs['Emission Color'].keyframe_insert('default_value', frame=F(t + dur))

GOLD = mat('gold', (1, .64, .14), 1, .25)
GLASS = mat('glass', (.75, .85, 1), 0, .05, trans=1)
DARK = mat('dark', (.02, .025, .035), 0, .55)
FLOOR = mat('floor', (.03, .035, .05), .3, .3)
STEEL = mat('steel', (.5, .52, .58), 1, .35)
PAPER = mat('paper', (.92, .93, .95), 0, .6, (.9, .92, 1), .6)
BAR = mat('bar', (.55, .6, .7), 0, .5)
RED = mat('red', (1, .1, .08), 0, .4, (1, .06, .03), 6)
WHITE = mat('white', (1, 1, 1), 0, .4, (1, 1, 1), 3)
BLACKT = mat('blackt', (.02, .02, .03), 0, .5)
ICE = mat('ice', (.6, .85, 1), 0, .05, (.3, .6, 1), .6, trans=1)
CYAN = mat('cyan', (.2, .7, 1), 0, .4, (.2, .6, 1), 4)

w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (.003, .005, .012, 1)
bpy.ops.mesh.primitive_plane_add(size=80); put(bpy.context.object, FLOOR)

# ---- Binance: a glass tower full of gold (far back) ----
TOWER = Vector((0, -16, 0))
cube(TOWER + Vector((0, 0, 5)), (2.4, 2.4, 5), GLASS)
for i in range(9):
    for j in range(3):
        cube(TOWER + Vector((-1.4 + j * 1.4, 0, .5 + i * 1.05)), (.6, 1.8, .45), GOLD)
title = text('$6.3B', TOWER + Vector((0, 2.8, 11.6)), 2.6, RED)
name = text('BINANCE', TOWER + Vector((0, 2.6, 10.4)), .9, WHITE)

# ---- two laptops on desks ----
def laptop(x, y):
    cube((x, y, .75), (1.1, .6, .05), DARK)                                         # desk
    for dx in (-1, 1): cube((x + dx, y, .35), (.05, .05, .35), STEEL)
    cube((x, y, .82), (.45, .3, .02), STEEL)                                        # base
    scrm = mat(f'scr{x}', (.1, .3, .6), 0, .3, (.15, .45, 1), 3)
    s = cube((x, y + .28, 1.1), (.44, .02, .28), scrm); s.rotation_euler = (math.radians(12), 0, 0)
    return s, scrm
LA, LA_M = laptop(-2.6, 2)
LB, LB_M = laptop(2.6, 2)

# ---- June: search results panel with an AD on top ----
SP = Vector((-2.6, 0.9, 2.6))
panel = cube(SP, (1.3, .03, .9), PAPER)
ad = cube(SP + Vector((0, .05, .5)), (1.1, .02, .14), RED)
adl = text('AD  ·  download tool', SP + Vector((1.0, .09, .5)), .16, WHITE, align='LEFT')
real = [cube(SP + Vector((0, .05, .15 - k * .32)), (1.1, .02, .11), BAR) for k in range(3)]
dl_bg = cube(SP + Vector((0, .05, -.95)), (1.1, .02, .05), BAR)
dl = cube(SP + Vector((1.1, .07, -.95)), (.001, .02, .05), RED)
for o in [panel, ad, adl, dl_bg, dl] + real: appear(o, bt('june'))
emit_to(RED, bt('ad'), (1, .06, .03), 14, .2); emit_to(RED, bt('ad') + .25, (1, .06, .03), 6, .3)
kf(dl, 'scale', bt('downloaded'), (.001, .02, .05)); kf(dl, 'scale', bt('downloaded') + 1.4, (1.1, .02, .05))
kf(dl, 'location', bt('downloaded'), tuple(SP + Vector((1.1, .07, -.95)))); kf(dl, 'location', bt('downloaded') + 1.4, tuple(SP + Vector((0, .07, -.95))))
emit_to(LA_M, bt('downloaded') + 1.3, (1, .08, .05), 5)

# ---- September: video call with a CEO who does not exist ----
CP = Vector((2.6, 0.9, 2.6))
call = cube(CP, (1.3, .03, .9), mat('callbg', (.05, .07, .12), 0, .5, (.04, .06, .12), 1))
head = bpy.ops.mesh.primitive_uv_sphere_add(radius=.32, location=CP + Vector((0, .1, .25))); head = put(bpy.context.object, BLACKT)
bpy.ops.mesh.primitive_cylinder_add(radius=.55, depth=.5, location=CP + Vector((0, .1, -.45))); body = put(bpy.context.object, BLACKT)
ceo = text('"CEO"', CP + Vector((0, .12, -.78)), .18, WHITE)
hire = text('JOB INTERVIEW', CP + Vector((0, .12, .72)), .17, CYAN)
for o in (call, head, body, ceo, hire): appear(o, bt('september'))
fake = text('DOES NOT EXIST', CP + Vector((0, .3, 0)), .26, RED)
appear(fake, bt('exist'), .25)
for o in (head, body): vanish(o, bt('exist'))
emit_to(LB_M, bt('code') + .3, (1, .08, .05), 5)

# ---- October 20: red links from both laptops to the 5 hot wallets ----
WAL = [Vector((x, -6.5, 0)) for x in (-4, -2, 0, 2, 4)]
vault_gold = []
for p in WAL:
    cube(p + Vector((0, 0, 1)), (.7, .7, 1), GLASS)
    g = cube(p + Vector((0, 0, .9)), (.55, .55, .9), GOLD); vault_gold.append(g)
    text('HOT WALLET', p + Vector((0, .75, 2.3)), .2, WHITE)
def beam(a, b, t):
    mid = (a + b) / 2; d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=.02, depth=d.length, location=mid); c = put(bpy.context.object, RED)
    c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); appear(c, t, .8, (1, 1, 1))
k = 0
for src in (Vector((-2.6, 1.7, 1.1)), Vector((2.6, 1.7, 1.1))):
    for j, p in enumerate(WAL):
        if (j + k) % 2 == 0: beam(src, p + Vector((0, .7, 1.2)), bt('twentieth') + .1 + j * .15)
    k += 1

# ---- October 29: one script, the wallets drain ----
for i, g in enumerate(vault_gold):
    t0 = bt('xrp') + i * .15
    kf(g, 'scale', t0, (.55, .55, .9)); kf(g, 'scale', t0 + 2.2, (.55, .55, .05))
    kf(g, 'location', t0, tuple(WAL[i] + Vector((0, 0, .9)))); kf(g, 'location', t0 + 2.2, tuple(WAL[i] + Vector((0, 0, .06))))
xrp = text('233,460,000 XRP', Vector((0, -5.2, 3.6)), .42, WHITE); appear(xrp, bt('xrp'))
four = text('4 MIN', Vector((0, -5.2, 3.0)), .34, RED); appear(four, bt('minutes1'))
for o in (xrp, four): vanish(o, bt('most'))
script = text('> run script', Vector((0, -2, 2.8)), .3, RED); appear(script, bt('script')); vanish(script, bt('xrp') + .3)
# tower drains too (the rest of the coins: bitcoin and more)
for i, ob in enumerate([o for o in bpy.data.objects if o.data and o.data.materials and o.data.materials[0] == GOLD and (o.location - TOWER).length < 6]):
    t0 = bt('bitcoin') + (i % 9) * .12
    kf(ob, 'scale', t0, tuple(ob.scale)); kf(ob, 'scale', t0 + 1.5, (0, 0, 0))

# ---- after: 20 minutes, $2.85B frozen, FBI ----
twenty = text('20 MIN', Vector((0, -5.2, 3.6)), .5, RED); appear(twenty, bt('twenty')); vanish(twenty, bt('froze') - .2)
for i in (0, 1):
    ic = cube(WAL[i] + Vector((0, 0, 1)), (.82, .82, 1.1), ICE); appear(ic, bt('froze') + i * .2, .5)
frz = text('$2.85B FROZEN', Vector((-3, -5.2, 3.0)), .38, CYAN); appear(frz, bt('froze') + .3)
fbi = text('FBI: NORTH KOREAN HACKERS', Vector((0, -5.2, 3.9)), .34, WHITE); appear(fbi, bt('fbi'))

# ---- lights ----
bpy.ops.object.light_add(type='AREA', location=(0, 6, 9)); l = bpy.context.object; l.data.energy = 1400; l.data.size = 10; l.data.color = (.6, .7, 1)
l.rotation_euler = (math.radians(35), 0, 0)
bpy.ops.object.light_add(type='POINT', location=TOWER + Vector((0, 4, 6))); l = bpy.context.object; l.data.energy = 2500; l.data.color = (1, .7, .3)
bpy.ops.object.light_add(type='POINT', location=(0, -4, 4)); al = bpy.context.object; al.data.color = (1, .05, .05)
al.data.energy = 0; al.data.keyframe_insert('energy', frame=1); al.data.keyframe_insert('energy', frame=F(bt('script')))
for i, t in enumerate(range(F(bt('script')), NF, 12)):
    al.data.energy = 0 if i % 2 else 1200; al.data.keyframe_insert('energy', frame=t)

# ---- camera: one continuous move, each stop keyed to the words ----
bpy.ops.object.empty_add(); aim = bpy.context.object
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam; cam.data.lens = 26
tc = cam.constraints.new('TRACK_TO'); tc.target = aim; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
shots = [(0, (0, -6, 9.5), TOWER + Vector((0, 0, 10.5))),
         (bt('started') - .3, (0, -9, 8), TOWER + Vector((0, 0, 9))),
         (bt('june') - .2, (-2.4, 5.6, 2.4), (-2.6, 1, 2.0)),
         (bt('september') - .4, (-1.2, 6, 2.4), (-1.3, 1, 2.0)),
         (bt('september') + .2, (2.4, 5.6, 2.4), (2.6, 1, 2.0)),
         (bt('twentieth') - .2, (0, 8.5, 6.5), (0, -2.5, 1.2)),
         (bt('twentieth') + 2.0, (0, 6, 5), (0, -4, 1.4)),
         (bt('xrp') - .2, (0, 1.5, 4.0), (0, -6, 2.2)),
         (bt('bitcoin'), (0, -4, 7), TOWER + Vector((0, 0, 5))),
         (bt('most') - .1, (0, 1.0, 4.0), (0, -6, 2.4)),
         (bt('fbi') - .1, (0, 2.0, 4.6), (0, -6, 3.0)),
         (bt('interview2') - .4, (-2.2, 5.0, 2.2), (-2.6, 2, 1.2)),
         (DUR, (-2.4, 4.4, 2.0), (-2.6, 2, 1.1))]
for t, cl, al_ in shots:
    kf(cam, 'location', t, tuple(cl)); kf(aim, 'location', t, tuple(al_))
for a in bpy.data.actions:
    for fc in a.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.easing = 'AUTO'

for fr in range(START, min(END, NF) + 1):
    sc.frame_set(fr); sc.render.filepath = f'{OUT}/f_{fr:04d}.png'
    bpy.ops.render.render(write_still=True)
print('rendered', START, END, 'of', NF)
