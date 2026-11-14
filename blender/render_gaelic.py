# Test harness: default scene -> run gaelic_soldiers_tiers.py -> verify parenting -> render lineup + close-ups.
import bpy, sys, os, math, runpy
args = sys.argv[sys.argv.index("--") + 1:]; script, out = args[0], args[1]
views = args[2].split(",") if len(args) > 2 else ["lineup", "c1", "c3", "c5"]
bpy.ops.wm.read_homefile(use_empty=False)
runpy.run_path(script, run_name="__main__")
# every generated mesh/text must hang off a soldier
orphans = [o.name for o in bpy.data.objects if o.type in {'MESH', 'FONT'} and o.parent is None and not o.name.startswith("Tier ")]
kids = {o.name: len(o.children) for o in bpy.data.objects if o.name.endswith("Soldier")}
print("PARENT_CHECK orphans:", orphans, "children per soldier:", kids)
os.makedirs(out, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "gaelic_soldiers_tiers.blend"))
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); sc.world = w
try:
    w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.34, 0.37, 0.4, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
except Exception: pass
for o in sc.objects:
    if o.type == 'LIGHT': o.data.energy = 3.5; o.rotation_euler = (math.radians(55), 0, math.radians(-35))
fd = bpy.data.lights.new("Fill", 'AREA'); fd.energy = 1200; fd.size = 10; fl = bpy.data.objects.new("Fill", fd); sc.collection.objects.link(fl); fl.location = (6, -7, 4); fl.rotation_euler = (math.radians(55), 0, 0)
gme = bpy.data.meshes.new("Floor"); gme.from_pydata([(-10, -10, 0), (25, -10, 0), (25, 10, 0), (-10, 10, 0)], [], [(0, 1, 2, 3)])
g = bpy.data.objects.new("Floor", gme); sc.collection.objects.link(g)
gm = bpy.data.materials.new("FloorMat"); gm.diffuse_color = (0.2, 0.2, 0.21, 1)
try:
    gm.use_nodes = True; gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.2, 0.2, 0.21, 1)
except Exception: pass
gme.materials.append(gm)
cam = sc.camera
for v in views:
    if v == "lineup":
        sc.render.resolution_x, sc.render.resolution_y = 1920, 820
        cam.location = (6.25, -12.5, 1.25); cam.rotation_euler = (math.radians(88), 0, 0); cam.data.lens = 28
    elif v.startswith("f"):
        i = int(v[1:]); x = (i - 1) * 2.5
        sc.render.resolution_x, sc.render.resolution_y = 900, 1100
        cam.location = (x + 0.55, -1.9, 1.5); cam.rotation_euler = (math.radians(86), 0, math.radians(16)); cam.data.lens = 50
    else:
        i = int(v[1:]); x = (i - 1) * 2.5 + 1.25
        sc.render.resolution_x, sc.render.resolution_y = 1500, 1000
        cam.location = (x + 0.6, -5.6, 1.35); cam.rotation_euler = (math.radians(86), 0, math.radians(6)); cam.data.lens = 34
    sc.render.filepath = os.path.join(out, "gaelic_%s.png" % v); bpy.ops.render.render(write_still=True); print("RENDERED", v)
