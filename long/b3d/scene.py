"""3D low-poly test scene (Blender, Cycles CPU). The Binance vault: a hooded hacker walks in, the vault opens, the coins drain into his laptop.
blender -b -P scene.py -- DURATION START END OUTDIR [preview]"""
import bpy, sys, math, random
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
DUR, START, END, OUT = float(argv[0]), int(argv[1]), int(argv[2]), argv[3]
PREVIEW = len(argv) > 4 and argv[4] == '1'
MID = len(argv) > 4 and argv[4] == 'mid'
FPS = 30; NF = int(DUR * FPS)
f = lambda s: 1 + int(s / 15.0 * NF)            # story beats are written on a 15 s clock and stretched to the real voice length
random.seed(4)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = 8 if PREVIEW else 14 if MID else 40; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4; sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = (360, 640) if PREVIEW else (540, 960) if MID else (720, 1280)
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, NF
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.image_settings.file_format = 'PNG'

def mat(name, color, metal=0., rough=.5, emit=None, strength=0.):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = strength
    return m
def obj(o, m, smooth=False):
    o.data.materials.append(m)
    if smooth:
        for p in o.data.polygons: p.use_smooth = True
    return o
def key(o, path, frame, value):
    setattr(o, path, value) if not isinstance(value, tuple) else setattr(o, path, value)
    o.keyframe_insert(data_path=path, frame=frame)
def ease_all():
    for a in bpy.data.actions:
        for fc in a.fcurves:
            for k in fc.keyframe_points: k.interpolation = 'BEZIER'; k.easing = 'AUTO'

GOLD = mat('gold', (1.0, .62, .12), 1, .28)
STEEL = mat('steel', (.55, .57, .62), 1, .35)
DARK = mat('dark', (.03, .035, .045), 0, .6)
FLOOR = mat('floor', (.05, .055, .07), .2, .35)
HOOD = mat('hood', (.06, .06, .07), 0, .8)
SKIN = mat('skin', (.02, .02, .02), 0, .9)
SCREEN = mat('screen', (.1, 1, .5), 0, .3, (.1, 1, .45), 6)
EYES = mat('eyes', (1, .2, .2), 0, .3, (1, .15, .1), 12)
REDL = mat('redtext', (1, .1, .1), 0, .3, (1, .08, .05), 7)
WHITE = mat('whitetext', (1, 1, 1), 0, .3, (1, .95, .85), 4)

# world + room
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (.004, .006, .012, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1
bpy.ops.mesh.primitive_plane_add(size=40); obj(bpy.context.object, FLOOR)
bpy.ops.mesh.primitive_cube_add(location=(0, -7, 4)); o = bpy.context.object; o.scale = (12, .3, 4); obj(o, DARK)          # back wall
for x in (-9, 9):
    bpy.ops.mesh.primitive_cube_add(location=(x, 0, 4)); o = bpy.context.object; o.scale = (.3, 8, 4); obj(o, DARK)
for x in (-7.5, -4.5, 4.5, 7.5):                                                                                    # pillars (none in front of the vault)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=.35, depth=8, location=(x, -6.2, 4)); obj(bpy.context.object, STEEL)

# vault door (hinged on the left)
bpy.ops.object.empty_add(location=(-2.3, -6.55, 2.6)); hinge = bpy.context.object
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=2.3, depth=.45, location=(0, -6.55, 2.6), rotation=(math.pi / 2, 0, 0)); door = obj(bpy.context.object, STEEL, True)
bpy.ops.mesh.primitive_torus_add(major_radius=1.5, minor_radius=.09, location=(0, -6.3, 2.6), rotation=(math.pi / 2, 0, 0)); ring = obj(bpy.context.object, GOLD, True)
for o in (door, ring):
    o.parent = hinge; o.matrix_parent_inverse = hinge.matrix_world.inverted()
key(hinge, 'rotation_euler', f(6.2), (0, 0, 0)); key(hinge, 'rotation_euler', f(8.0), (0, 0, math.radians(-105)))
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=2.15, depth=.2, location=(0, -6.82, 2.6), rotation=(math.pi / 2, 0, 0)); obj(bpy.context.object, mat('inside', (1, .7, .25), 0, .5, (1, .55, .15), 2.5))

# coins: a heap in front of the vault + the ones that fly into the laptop
coins = []
bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=.16, depth=.035); proto = obj(bpy.context.object, GOLD, True); proto.location = (0, 0, -5)
for i in range(260):
    r = random.random() ** .7 * 2.6; a = random.random() * 6.28
    h = max(0, 1.0 - r / 2.6) * 1.2
    c = proto.copy(); c.data = proto.data; sc.collection.objects.link(c)
    c.location = (math.cos(a) * r, -4.6 + math.sin(a) * r * .55, .02 + random.random() * h)
    c.rotation_euler = (random.uniform(-.6, .6), random.uniform(-.6, .6), random.random() * 6)
    coins.append(c)

# the hacker: hooded figure, glowing eyes, laptop. Walks in from the right, stops at the heap.
bpy.ops.object.empty_add(location=(5.5, 3.5, 0)); rig = bpy.context.object
def part(add, m, **kw):
    add(**kw); o = bpy.context.object; obj(o, m, True); o.parent = rig; return o
body = part(bpy.ops.mesh.primitive_cylinder_add, HOOD, vertices=16, radius=.42, depth=1.25, location=(0, 0, 1.45)); body.scale = (1, .75, 1)
part(bpy.ops.mesh.primitive_cone_add, HOOD, vertices=16, radius1=.4, radius2=.06, depth=.9, location=(0, .1, 2.5))
part(bpy.ops.mesh.primitive_uv_sphere_add, SKIN, radius=.27, location=(0, -.14, 2.25))
for x in (-.1, .1): part(bpy.ops.mesh.primitive_uv_sphere_add, EYES, radius=.05, location=(x, -.4, 2.28))
for x in (-.38, .38):
    a_ = part(bpy.ops.mesh.primitive_cylinder_add, HOOD, vertices=10, radius=.1, depth=.7, location=(x * .9, -.3, 1.6)); a_.rotation_euler = (math.radians(70), 0, 0)
legs = []
for x in (-.18, .18):
    bpy.ops.object.empty_add(location=(x, 0, .85)); hip = bpy.context.object; hip.parent = rig
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=.13, depth=.85, location=(x, 0, .43)); lg = obj(bpy.context.object, HOOD, True)
    lg.parent = hip; lg.matrix_parent_inverse = hip.matrix_world.inverted(); legs.append(hip)
lap = part(bpy.ops.mesh.primitive_cube_add, DARK, location=(0, -.55, 1.45)); lap.scale = (.35, .25, .02)
scr = part(bpy.ops.mesh.primitive_cube_add, SCREEN, location=(0, -.42, 1.62)); scr.scale = (.34, .02, .2); scr.rotation_euler = (math.radians(-20), 0, 0)
bpy.ops.object.light_add(type='POINT', location=(0, -.9, 1.7)); gl = bpy.context.object; gl.data.color = (.2, 1, .5); gl.data.energy = 60; gl.parent = rig
# walk path
stop = (1.6, -1.6, 0)
face = lambda dx, dy: (0, 0, math.atan2(dx, -dy))                              # the figure looks along -Y
key(rig, 'rotation_euler', 1, face(stop[0] - 5.5, stop[1] - 3.5)); key(rig, 'rotation_euler', f(6.0), face(stop[0] - 5.5, stop[1] - 3.5))
key(rig, 'rotation_euler', f(7.0), face(0 - stop[0], -4.6 - stop[1]))
key(rig, 'location', 1, (5.5, 3.5, 0)); key(rig, 'location', f(3.0), (5.5, 3.5, 0)); key(rig, 'location', f(6.0), stop)
for k in range(f(3.0), f(6.0), 6):                                                           # leg swing while walking
    for j, hip in enumerate(legs):
        hip.rotation_euler = (math.radians(28 if (k // 6 + j) % 2 else -28), 0, 0); hip.keyframe_insert('rotation_euler', frame=k)
for hip in legs:
    hip.rotation_euler = (0, 0, 0); hip.keyframe_insert('rotation_euler', frame=f(6.1))

# coins fly into the laptop (8.5 s -> 13 s), the heap sinks
target = Vector(stop) + Vector((0, -.5, 1.55))
fly = random.sample(coins, 150)
for i, c in enumerate(fly):
    t0 = f(8.3 + (i / len(fly)) * 3.6); t1 = t0 + int(.7 * FPS)
    key(c, 'location', t0, tuple(c.location)); key(c, 'scale', t0, (1, 1, 1))
    mid = (Vector(c.location) + target) / 2 + Vector((random.uniform(-.5, .5), 0, 1.4))
    key(c, 'location', (t0 + t1) // 2, tuple(mid)); key(c, 'location', t1, tuple(target)); key(c, 'scale', t1, (.05, .05, .05))
    key(c, 'rotation_euler', t1, (c.rotation_euler[0] + 6, c.rotation_euler[1] + 4, 0))

# 3D titles: "$6.3B" (hook, and again at the end for the loop) and "20 MIN"
def title(txt, m, loc, size):
    bpy.ops.object.text_add(location=loc, rotation=(math.radians(80), 0, math.pi)); t = bpy.context.object
    t.data.body = txt; t.data.align_x = 'CENTER'; t.data.size = size; t.data.extrude = .08; t.data.bevel_depth = .01
    try: t.data.font = bpy.data.fonts.load('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    except Exception: pass
    obj(t, m); return t
big = title('$6.3B', REDL, (0, -4.2, 3.3), 1.5)
mins = title('20 MIN', WHITE, (0, -4.2, 2.25), .6)
def show(o, frames):                                                                          # visibility windows by scaling
    o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=1)
    for a, b in frames:
        o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=max(1, a - 6))
        o.scale = (1, 1, 1); o.keyframe_insert('scale', frame=a); o.keyframe_insert('scale', frame=b)
        o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=b + 6)
show(big, [(1, f(2.6)), (f(12.6), NF)])
show(mins, [(f(1.3), f(2.6))])

# lights: cool key, warm vault glow, red alarm blinking after the vault opens
bpy.ops.object.light_add(type='AREA', location=(4, 4, 7)); k = bpy.context.object; k.data.energy = 900; k.data.size = 6; k.data.color = (.6, .7, 1)
k.rotation_euler = (math.radians(50), 0, math.radians(135))
bpy.ops.object.light_add(type='POINT', location=(0, -5.2, 2.6)); vg = bpy.context.object; vg.data.color = (1, .6, .2)
vg.data.energy = 0; vg.data.keyframe_insert('energy', frame=f(6.2)); vg.data.energy = 900; vg.data.keyframe_insert('energy', frame=f(8.0))
for x in (-7, 7):
    bpy.ops.object.light_add(type='POINT', location=(x, -4, 6)); al = bpy.context.object; al.data.color = (1, .05, .05)
    for i, t in enumerate(range(f(8.5), NF, 12)):
        al.data.energy = 0 if i % 2 else 1500; al.data.keyframe_insert('energy', frame=t)
    al.data.energy = 0; al.data.keyframe_insert('energy', frame=1); al.data.keyframe_insert('energy', frame=f(8.4))

# camera: starts on the $6.3B title (hook), swings to the hacker walking in, over the shoulder at the vault, pulls back to the title (loop)
bpy.ops.object.empty_add(location=(0, -4.2, 3.0)); aim = bpy.context.object
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam; cam.data.lens = 28
tc = cam.constraints.new('TRACK_TO'); tc.target = aim; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
shots = [(0, (0, 1.2, 3.4), (0, -4.2, 3.0)), (2.8, (0, 2.6, 3.0), (0, -4.2, 2.6)), (3.4, (1.5, 5.5, 2.4), (5.5, 3.5, 1.6)),
         (6.0, (4.2, 1.5, 2.2), (1.6, -1.6, 1.6)), (8.5, (3.4, .4, 2.0), (0, -4.8, 1.6)), (12.4, (0, 2.0, 3.8), (0, -4.2, 2.8)), (15.0, (0, 1.2, 3.4), (0, -4.2, 3.0))]
for t, cl, al in shots:
    key(cam, 'location', f(t), cl); key(aim, 'location', f(t), al)
ease_all()

for fr in range(START, min(END, NF) + 1):
    sc.frame_set(fr); sc.render.filepath = f'{OUT}/f_{fr:04d}.png'
    bpy.ops.render.render(write_still=True)
print('rendered', START, END, 'of', NF)
