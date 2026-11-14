# Renders the pasted material (default ramp) beside the tightened version on the same procedural hill.
import bpy, bmesh, sys, os, math, runpy
from mathutils import Vector, noise
out = sys.argv[sys.argv.index("--") + 1]; here = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
ns = runpy.run_path(os.path.join(here, "landscape_material.py"), run_name="lib")
sc = bpy.context.scene

def hill(name, x0):
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=160, y_segments=160, size=10)
    for v in bm.verts:
        p = v.co; r = math.hypot(p.x, p.y)
        h = 3.2 * math.exp(-(r / 4.2) ** 2) + 1.4 * max(0, 1 - abs(p.x + 1.5) / 1.2) * math.exp(-(p.y / 5) ** 2)   # mound + steep ridge
        h += 0.35 * noise.fractal(Vector((p.x * 0.35, p.y * 0.35, 0)), 0.5, 2.0, 5)
        v.co.z = h
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(name, me); ob.location.x = x0; sc.collection.objects.link(ob); return ob

orig = ns["create_landscape_material"](grass_from=1.0, rock_below=0.0)   # identical to the pasted script's default ramp
orig.name = "Pasted (default ramp)"
tight = ns["create_landscape_material"]()
for ob, m in ((hill("HillA", -11), orig), (hill("HillB", 11), tight)): ob.data.materials.append(m)
sc.render.engine = 'CYCLES'; sc.cycles.samples = 48; sc.render.resolution_x, sc.render.resolution_y = 1600, 700
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.6, 0.75, 1)
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN')); sun.data.energy = 4; sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, -30, 15); cam.rotation_euler = ((Vector((0, 0, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()); cam.data.lens = 32
for txt, x in (("pasted: default ramp", -11), ("ramp 0.72 - 0.86", 11)):
    cu = bpy.data.curves.new("L", 'FONT'); cu.body = txt; cu.size = 1.0; cu.align_x = 'CENTER'
    t = bpy.data.objects.new("L", cu); t.location = (x, -9, 6.2); t.rotation_euler = (math.radians(63), 0, 0); sc.collection.objects.link(t)
sc.render.filepath = os.path.join(out, "landscape_material_test.png"); bpy.ops.render.render(write_still=True); print("RENDERED")
