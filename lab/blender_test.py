# blender -b -P lab/blender_test.py   (headless, CPU only). Low-poly "crypto city" with a camera fly-through.
import bpy, math, random, time, os, sys
random.seed(7)
engine = os.environ.get('ENGINE', 'WORKBENCH'); W, Hh, frames = 540, 960, int(os.environ.get('FRAMES', 24))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.resolution_x, sc.render.resolution_y = W, Hh; sc.render.resolution_percentage = 100
sc.render.engine = {'WORKBENCH': 'BLENDER_WORKBENCH', 'CYCLES': 'CYCLES', 'EEVEE': 'BLENDER_EEVEE_NEXT'}.get(engine, 'BLENDER_WORKBENCH')
if engine == 'CYCLES':
    sc.cycles.samples = 12; sc.cycles.use_denoising = False; sc.cycles.device = 'CPU'
if engine == 'WORKBENCH':
    sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_shadows = True
    sc.display.shading.show_cavity = True
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = True
sc.world.node_tree.nodes['Background'].inputs[0].default_value = (0.02, 0.03, 0.06, 1)
def mat(name, rgb):
    m = bpy.data.materials.new(name); m.diffuse_color = (*rgb, 1); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (*rgb, 1)
    return m
cols = [mat(f'c{i}', c) for i, c in enumerate([(0.1, 0.8, 0.6), (0.9, 0.7, 0.2), (0.2, 0.4, 0.9), (0.9, 0.2, 0.3)])]
for x in range(-6, 7):
    for y in range(-14, 3):
        h = random.choice([0.5, 1, 1.5, 2.5, 4, 6]) * (1 + random.random())
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x * 1.3, y * 1.3, h / 2)); o = bpy.context.object
        o.scale = (0.5, 0.5, h); o.data.materials.append(random.choice(cols))
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); bpy.context.object.data.materials.append(mat('floor', (0.05, 0.06, 0.1)))
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10)); bpy.context.object.data.energy = 3; bpy.context.object.rotation_euler = (0.9, 0.2, 0.6)
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
sc.frame_start, sc.frame_end = 1, frames
for f in range(1, frames + 1):
    t = (f - 1) / max(1, frames - 1)
    cam.location = (math.sin(t * 1.2) * 3, 2 - t * 16, 3.2 + t); cam.rotation_euler = (math.radians(78), 0, math.radians(math.sin(t * 1.2) * -10))
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
os.makedirs('sample_out/blender', exist_ok=True)
t0 = time.time(); sc.render.image_settings.file_format = 'PNG'; os.makedirs('sample_out', exist_ok=True)
for f in (1, frames // 2, frames):
    sc.frame_set(f); sc.render.filepath = os.path.abspath(f'sample_out/blender_{engine}_{f}.png'); bpy.ops.render.render(write_still=True)
dt = (time.time() - t0) / 3
print(f'::notice title=blender-{engine}::BLENDER {engine} {W}x{Hh}: {dt:.2f} s per frame -> {dt * 60 * 40 / 60:.1f} min for a 40 s video at 60 fps, {dt * 30 * 40 / 60:.1f} min at 30 fps')
