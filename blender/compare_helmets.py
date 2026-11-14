# Side-by-side: our helmet with the procedural iron (refine_viking_assets) vs the Tripo AI-textured version.
import bpy, sys, os, math, runpy
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]; ours, tripo, refine, out = a[:4]; photo = a[4] if len(a) > 4 else None
bpy.ops.wm.read_factory_settings(use_empty=True)
R = runpy.run_path(refine, run_name="refine_lib")            # reuse the procedural material builders
def imp(path):
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
def fit(objs, x):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector(map(min, *pts)) if False else Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    s = 0.3 / max(hi - lo); c = (lo + hi) / 2
    for o in objs:
        o.matrix_world = __import__("mathutils").Matrix.Translation((x, 0, 0)) @ __import__("mathutils").Matrix.Scale(s, 4) @ __import__("mathutils").Matrix.Translation(-Vector((c.x, c.y, lo.z))) @ o.matrix_world
    return lo, hi
A = imp(ours); B = imp(tripo)
print("IMPORTED ours", [o.name for o in A], "tripo", [o.name for o in B], "tripo mats", [s.material.name for o in B for s in o.material_slots if s.material])
m = bpy.data.materials.new("Iron/Steel"); m.diffuse_color = (0.42, 0.43, 0.45, 1); R["rebuild_material"](m)
for o in A:
    o.data.materials.clear(); o.data.materials.append(m)
    for p in o.data.polygons: p.use_smooth = True
if photo:
    C = imp(photo); fit(A, -0.38); fit(B, 0.0); fit(C, 0.38)
else:
    fit(A, -0.2); fit(B, 0.2)
for o in B: o.rotation_euler.z += 0.0
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 96; sc.render.resolution_x, sc.render.resolution_y = (1800, 700) if photo else (1600, 800)
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.055, 0.06, 1)
for name, loc, e, size in (("Key", (-0.9, -1.2, 1.0), 120, 1.2), ("Fill", (1.0, -1.0, 0.4), 40, 1.5), ("Rim", (0.0, 1.2, 1.0), 90, 1.0)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = e; ld.size = size; ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob); ob.location = loc
    ob.rotation_euler = (Vector((0, 0, 0.15)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
cd = bpy.data.cameras.new("Cam"); cd.lens = 85; cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, -3.4 if photo else -2.5, 0.42); cam.rotation_euler = (Vector((0, 0, 0.14)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = os.path.join(out, "helmet_compare3_front.png" if photo else "helmet_compare_front.png"); bpy.ops.render.render(write_still=True); print("RENDERED front")
cam.location = (1.9 if photo else 1.6, -2.6 if photo else -1.9, 0.62); cam.rotation_euler = (Vector((0, 0, 0.14)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = os.path.join(out, "helmet_compare3_angle.png" if photo else "helmet_compare_angle.png"); bpy.ops.render.render(write_still=True); print("RENDERED angle")