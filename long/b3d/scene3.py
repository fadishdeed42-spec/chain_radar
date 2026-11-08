"""Binance $6.3B hack, v3: people at real screens (animated UI from ui.py), one continuous camera keyed to the voice (beats.json).
blender -b -P scene3.py -- DUR START END OUTDIR UIDIR [mid|check]    GPU (OptiX/CUDA) is used when there is one."""
import bpy, sys, math, json, os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
argv = sys.argv[sys.argv.index('--') + 1:]
DUR, START, END, OUT, UI = float(argv[0]), int(argv[1]), int(argv[2]), argv[3], argv[4]
MODE = argv[5] if len(argv) > 5 else ''
FPS = 30; NF = int(DUR * FPS)
B = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'beats.json')))
F = lambda s: max(1, int(round(s * FPS)) + 1)
bt = lambda k: B[k]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4; sc.cycles.transmission_bounces = 4; sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = (540, 960) if MODE == 'mid' else (1080, 1920)
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, NF
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 95
GPU = False
try:
    pr = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA'):
        try:
            pr.compute_device_type = kind; pr.get_devices()
            devs = [d for d in pr.devices if d.type == kind]
            if devs:
                for d in pr.devices: d.use = d.type == kind
                GPU = True; print('GPU', kind, [d.name for d in devs]); break
        except Exception as e: print('no', kind, e)
except Exception as e: print('gpu setup', e)
sc.cycles.device = 'GPU' if GPU else 'CPU'
sc.cycles.samples = 96 if GPU else 14
if GPU: sc.cycles.denoiser = 'OPTIX' if pr.compute_device_type == 'OPTIX' else 'OPENIMAGEDENOISE'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
if not os.path.exists(FONT): FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../studio/fonts/InterDisplay-ExtraBold.otf')

def mat(name, color, metal=0., rough=.5, emit=None, strength=0., trans=0., sheen=0.):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    b.inputs['Transmission Weight'].default_value = trans; b.inputs['Sheen Weight'].default_value = sheen
    if emit: b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = strength
    return m
def screen_mat(name, folder, strength=2.2):            # an image sequence played as a glowing screen
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    img = bpy.data.images.load(os.path.join(UI, folder, '0001.jpg')); img.source = 'SEQUENCE'
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
    tex.image_user.frame_duration = NF; tex.image_user.frame_start = 1; tex.image_user.frame_offset = 0; tex.image_user.use_auto_refresh = True
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m
def put(o, m):
    o.data.materials.append(m); return o
def smooth(o, bev=0.):
    if bev:
        b = o.modifiers.new('b', 'BEVEL'); b.width = bev; b.segments = 3
    for p in o.data.polygons: p.use_smooth = True
    return o
def cube(loc, scale, m, bev=.02):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.scale = scale
    o.data.materials.append(m)
    if bev:
        b = o.modifiers.new('b', 'BEVEL'); b.width = bev; b.segments = 2; b.affect = 'EDGES'
    return o
def plane(loc, half, m, rot=(math.radians(90), 0, math.pi)):          # faces +Y (the camera side); image upright
    bpy.ops.mesh.primitive_plane_add(location=loc, rotation=rot); o = bpy.context.object; o.scale = (half[0], half[1], 1); return put(o, m)
def text(body, loc, size, m, rot=(math.radians(90), 0, math.pi)):
    bpy.ops.object.text_add(location=loc, rotation=rot); t = bpy.context.object
    t.data.body = body; t.data.align_x = 'CENTER'; t.data.align_y = 'CENTER'; t.data.size = size; t.data.extrude = .03; t.data.bevel_depth = .006
    try: t.data.font = bpy.data.fonts.load(FONT)
    except Exception: pass
    return put(t, m)
def kf(o, path, t, v):
    setattr(o, path, v); o.keyframe_insert(data_path=path, frame=F(t))
TEXTS = []                                                            # (object, visible from, visible to) for the safe-frame check
def appear(o, t, dur=.35, until=None):
    s = tuple(o.scale); kf(o, 'scale', 0, (0, 0, 0)); kf(o, 'scale', max(0, t - .01), (0, 0, 0)); kf(o, 'scale', t + dur, s)
    if until: kf(o, 'scale', until, s); kf(o, 'scale', until + .3, (0, 0, 0))
    if o.type == 'FONT': TEXTS.append((o, t + dur, until or DUR))

GOLD = mat('gold', (1, .64, .14), 1, .22)
GLASS = mat('glass', (.75, .85, 1), 0, .03, trans=1)
DESK = mat('desk', (.16, .1, .06), 0, .45)
FLOOR = mat('floor', (.025, .03, .04), .2, .25)
ALU = mat('alu', (.62, .64, .68), 1, .3)
BLACK = mat('black', (.015, .015, .02), 0, .4)
HOOD1 = mat('hood1', (.05, .07, .11), 0, .85, sheen=.4)
HOOD2 = mat('hood2', (.12, .05, .05), 0, .85, sheen=.4)
SKIN = mat('skin', (.55, .38, .28), 0, .55)
HAIR = mat('hair', (.03, .02, .015), 0, .6)
RED = mat('red', (1, .1, .08), 0, .4, (1, .06, .03), 8)
WHITE = mat('white', (1, 1, 1), 0, .4, (1, 1, 1), 4)
ICE = mat('ice', (.6, .85, 1), 0, .05, (.3, .6, 1), .8, trans=1)
CYAN = mat('cyan', (.2, .7, 1), 0, .4, (.2, .6, 1), 5)

w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (.004, .006, .014, 1)
bpy.ops.mesh.primitive_plane_add(size=80); put(bpy.context.object, FLOOR)

# ---- Binance: glass tower of gold, far back ----
TOWER = Vector((0, -16, 0))
cube(TOWER + Vector((0, 0, 5)), (2.4, 2.4, 5), GLASS, 0)
GOLDBARS = []
for i in range(9):
    for j in range(3):
        GOLDBARS.append(cube(TOWER + Vector((-1.4 + j * 1.4, 0, .5 + i * 1.05)), (.6, 1.8, .45), GOLD))
t63 = text('$6.3B', TOWER + Vector((0, 2.8, 11.6)), 2.6, RED); TEXTS.append((t63, 0, bt('june')))
tbn = text('BINANCE', TOWER + Vector((0, 2.6, 10.3)), .9, WHITE); TEXTS.append((tbn, 0, bt('june')))

# ---- a person at a laptop (seen from behind / over the shoulder) ----
def person(x, y, hood, tag):
    root = bpy.data.objects.new('p' + tag, None); bpy.context.collection.objects.link(root); root.location = (x, y, 0)
    def part(o): o.parent = root; o.location = o.location - Vector((x, y, 0)); return o
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.24, location=(x, y + .02, 1.18), segments=32, ring_count=16); torso = bpy.context.object
    torso.scale = (1, .62, 1.45); smooth(put(torso, hood)); part(torso)
    for s in (-1, 1):                                               # upper + lower arm reaching to the keyboard
        bpy.ops.mesh.primitive_cylinder_add(radius=.06, depth=.36, location=(x + s * .25, y - .1, 1.2)); a = bpy.context.object
        a.rotation_euler = (math.radians(-35), 0, s * math.radians(-12)); smooth(put(a, hood), .04); part(a)
        bpy.ops.mesh.primitive_cylinder_add(radius=.05, depth=.34, location=(x + s * .17, y - .36, .98)); f = bpy.context.object
        f.rotation_euler = (math.radians(-85), 0, s * math.radians(25)); smooth(put(f, hood), .03); part(f)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.045, location=(x + s * .1, y - .52, .93)); smooth(put(bpy.context.object, SKIN)); part(bpy.context.object)
    hp = bpy.data.objects.new('h' + tag, None); bpy.context.collection.objects.link(hp); hp.parent = root; hp.location = (0, 0, 1.5)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.13, location=(0, 0, 0), segments=32, ring_count=16); hd = bpy.context.object
    hd.scale = (.92, 1, 1.12); smooth(put(hd, HAIR)); hd.parent = hp; hd.location = (0, 0, .12)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.16, location=(0, 0, 0), segments=32, ring_count=16); hh = bpy.context.object   # hood
    hh.scale = (1, 1.05, 1.05); smooth(put(hh, hood)); hh.parent = hp; hh.location = (0, .05, .1)
    bpy.ops.mesh.primitive_cylinder_add(radius=.05, depth=.12, location=(0, 0, 0)); nk = bpy.context.object; smooth(put(nk, SKIN)); nk.parent = hp; nk.location = (0, 0, -.03)
    cube((x, y + .12, .55), (.24, .22, .04), BLACK, .02); cube((x, y + .33, .9), (.24, .03, .32), BLACK, .02)   # chair
    cube((x, y + .12, .27), (.03, .03, .27), ALU, 0)
    return root, hp, torso
def laptop(x, y, folder):                                          # desk, keyboard and a big monitor
    cube((x, y, .74), (1.0, .55, .03), DESK, .01)
    for dx in (-.9, .9):
        for dy in (-.45, .45): cube((x + dx, y + dy, .36), (.03, .03, .36), ALU, 0)
    cube((x, y + .3, .785), (.3, .1, .012), BLACK, .006)                                    # keyboard
    cube((x, y - .25, .9), (.04, .03, .15), ALU, .01); cube((x, y - .25, .78), (.18, .12, .01), ALU, .005)   # stand
    cube((x, y - .27, 1.25), (.6, .02, .38), BLACK, .015)                                   # bezel
    return plane((x, y - .245, 1.25), (.56, .35), screen_mat('scr' + folder, folder))
SA = laptop(-2.4, 2, 'a'); SB = laptop(2.4, 2, 'b')
PA, HA, TA = person(-2.4, 2.75, HOOD1, 'A'); PB, HB, TB = person(2.4, 2.75, HOOD2, 'B')
for hp, tor, ph in ((HA, TA, 0), (HB, TB, 1.3)):                 # breathing + small head moves while working
    for k in range(0, int(DUR) + 1, 2):
        kf(tor, 'scale', k + ph % 2, (1, .62, 1.45)); kf(tor, 'scale', k + 1 + ph % 2, (1.015, .63, 1.47))
        kf(hp, 'rotation_euler', k + ph, (math.radians(-6 + 3 * math.sin(k)), 0, math.radians(4 * math.sin(k * 1.7))))
for hp, t0 in ((HA, bt('twentieth') + .2), (HB, bt('twentieth') + .35)):   # leans back when the screen is taken over
    kf(hp, 'rotation_euler', t0, (math.radians(-4), 0, 0)); kf(hp, 'rotation_euler', t0 + .4, (math.radians(10), 0, math.radians(8)))
    kf(hp, 'rotation_euler', t0 + 3.0, (math.radians(10), 0, math.radians(8)))

# ---- hot wallets: 5 glass vaults with gold + a big wall display ----
WAL = [Vector((x, -6.5, 0)) for x in (-4, -2, 0, 2, 4)]
vault_gold = []
for p in WAL:
    cube(p + Vector((0, 0, 1)), (.7, .7, 1), GLASS, 0)
    vault_gold.append(cube(p + Vector((0, 0, .9)), (.55, .55, .9), GOLD))
WALL = Vector((0, -5.6, 4.3))
cube(WALL - Vector((0, .08, 0)), (2.5, .05, 1.6), BLACK, .02)
plane(WALL, (2.4, 1.5), screen_mat('wall', 'w', 2.6))
def beam(a, b, t):
    mid = (a + b) / 2; d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=.025, depth=d.length, location=mid); c = put(bpy.context.object, RED)
    c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); s = tuple(c.scale)
    kf(c, 'scale', 0, (0, 0, 0)); kf(c, 'scale', t, (0, 0, 0)); kf(c, 'scale', t + .8, s)
beam(Vector((-2.4, 1.7, 1.25)), WALL + Vector((-1, .05, -1.4)), bt('twentieth') + .1)
beam(Vector((2.4, 1.7, 1.25)), WALL + Vector((1, .05, -1.4)), bt('twentieth') + .25)
for i, g in enumerate(vault_gold):                               # Oct 29: the vaults drain while the wall counts the XRP
    t0 = bt('xrp') + i * .15
    kf(g, 'scale', t0, (.55, .55, .9)); kf(g, 'scale', t0 + 2.4, (.55, .55, .04))
    kf(g, 'location', t0, tuple(WAL[i] + Vector((0, 0, .9)))); kf(g, 'location', t0 + 2.4, tuple(WAL[i] + Vector((0, 0, .05))))
for i, ob in enumerate(GOLDBARS):                                # then bitcoin and more: the tower empties
    t0 = bt('bitcoin') + (i % 9) * .1
    kf(ob, 'scale', t0, tuple(ob.scale)); kf(ob, 'scale', t0 + 1.4, (0, 0, 0))
for i in range(5):                                               # $2.85B frozen: ice over the vaults
    ic = cube(WAL[i] + Vector((0, 0, 1)), (.82, .82, 1.1), ICE, .05); appear(ic, bt('froze') + i * .12, .5)
frz = text('$2.85B FROZEN', WALL + Vector((0, 1.2, -2.15)), .42, CYAN); appear(frz, bt('froze') + .3, .35, bt('fbi') - .3)
fbi = text('FBI: NORTH KOREAN HACKERS', WALL + Vector((0, 1.2, -2.15)), .3, WHITE); appear(fbi, bt('fbi'), .35, bt('interview2') - .5)

# ---- light ----
bpy.ops.object.light_add(type='AREA', location=(0, 7, 8)); l = bpy.context.object; l.data.energy = 900; l.data.size = 10; l.data.color = (.55, .65, 1)
l.rotation_euler = (math.radians(40), 0, 0)
bpy.ops.object.light_add(type='POINT', location=TOWER + Vector((0, 4, 6))); l = bpy.context.object; l.data.energy = 2500; l.data.color = (1, .7, .3)
for x in (-2.4, 2.4):                                            # rim light on each person
    bpy.ops.object.light_add(type='AREA', location=(x, 4.2, 2.4)); l = bpy.context.object; l.data.energy = 60; l.data.size = 1; l.data.color = (.5, .7, 1)
    l.rotation_euler = (math.radians(60), 0, math.pi)
bpy.ops.object.light_add(type='POINT', location=(0, -3.5, 4)); al = bpy.context.object; al.data.color = (1, .05, .05)
al.data.energy = 0; al.data.keyframe_insert('energy', frame=1); al.data.keyframe_insert('energy', frame=F(bt('script')))
for i, t in enumerate(range(F(bt('script')), NF, 15)):
    al.data.energy = 0 if i % 2 else 900; al.data.keyframe_insert('energy', frame=t)

# ---- camera: one continuous move ----
bpy.ops.object.empty_add(); aim = bpy.context.object
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam; cam.data.lens = 30
cam.data.dof.use_dof = True; cam.data.dof.focus_object = aim; cam.data.dof.aperture_fstop = 2.8
tc = cam.constraints.new('TRACK_TO'); tc.target = aim; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
SCRA, SCRB = Vector((-2.4, 1.75, 1.25)), Vector((2.4, 1.75, 1.25))
shots = [(0, (0, -7, 9.5), TOWER + Vector((0, 0, 10.6))),                         # $6.3B left Binance
         (bt('started') - .3, (0, -9.5, 8), TOWER + Vector((0, 0, 9))),
         (bt('june') - .5, (-1.0, 4.9, 2.3), (-2.4, 2.4, 1.2)),                  # over her shoulder
         (bt('june') + .6, (-1.7, 3.75, 1.75), SCRA),                            # the search page
         (bt('september') - .7, (-1.72, 3.65, 1.72), SCRA),
         (bt('september') - .1, (1.0, 4.9, 2.3), (2.4, 2.4, 1.2)),
         (bt('september') + .9, (3.1, 3.75, 1.75), SCRB),                        # the video call
         (bt('twentieth') - .5, (3.08, 3.65, 1.72), SCRB),
         (bt('twentieth') + .3, (0, 6.8, 4.5), (0, 1.2, 1.3)),                    # both screens taken over
         (bt('script') - 1.0, (0, 6.5, 4.2), (0, -3.5, 2.6)),                     # to the wallets
         (bt('script') - .1, (0, 2.9, 3.9), WALL + Vector((0, 0, -.6))),          # the wall: script, XRP, 4 minutes
         (bt('bitcoin') - .2, (0, 1.5, 4.6), WALL + Vector((0, 0, -.8))),
         (bt('bitcoin') + .4, (0, -4, 7), TOWER + Vector((0, 0, 5))),             # tower empties
         (bt('most') + .2, (0, -4.5, 6.5), TOWER + Vector((0, 0, 4))),
         (bt('froze') - .3, (0, 2.6, 2.6), (0, -6.5, 1.3)),                      # frozen vaults
         (bt('fbi') + 1.5, (0, 2.0, 2.8), (0, -6.5, 1.5)),
         (bt('interview2') - .7, (-1.0, 4.9, 2.3), (-2.4, 2.4, 1.2)),             # back to the job interview
         (DUR, (-1.5, 4.3, 1.9), (-2.4, 2.2, 1.1))]
for t, cl, al_ in shots:
    kf(cam, 'location', t, tuple(cl)); kf(aim, 'location', t, tuple(al_))
for a in bpy.data.actions:
    for fc in a.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.easing = 'AUTO'

# ---- safe-frame check: every 3D label fully inside the frame (with a 6% margin) while it is on screen ----
def safe_check():
    bad = {}
    for o, t0, t1 in TEXTS:
        for fr in range(F(t0), min(NF, F(t1)) + 1, 3):
            sc.frame_set(fr)
            if min(o.scale) < .5 * max(o.scale): continue
            for c in o.bound_box:
                v = world_to_camera_view(sc, cam, o.matrix_world @ Vector(c))
                if v.z > 0 and not (.06 < v.x < .94 and .06 < v.y < .94):
                    bad.setdefault(o.data.body, []).append(round((fr - 1) / FPS, 1)); break
    return {k: [v[0], v[-1], len(v)] for k, v in bad.items()}
if MODE == 'check' or START == 1:
    rep = safe_check(); print('SAFE_FRAME', json.dumps(rep)); os.makedirs(OUT, exist_ok=True)
    json.dump(rep, open(os.path.join(OUT, 'safe.json'), 'w'))
if MODE == 'check': sys.exit(0)

for fr in range(START, min(END, NF) + 1):
    sc.frame_set(fr); sc.render.filepath = f'{OUT}/f_{fr:04d}.jpg'
    bpy.ops.render.render(write_still=True)
print('rendered', START, END, 'of', NF)
