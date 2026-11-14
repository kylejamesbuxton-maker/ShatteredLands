# Test harness: runs viking_armor_tiers.py in a clean scene, saves the .blend and renders lineup + close-ups.
import bpy, sys, os, math, runpy
args = sys.argv[sys.argv.index("--") + 1:]; script, out = args[0], args[1]
bpy.ops.wm.read_homefile(use_empty=False)          # default scene (cube, light, camera) — proves clear_scene() works
runpy.run_path(script, run_name="__main__")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "viking_armor_tiers.blend"))
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'; sc.render.resolution_x, sc.render.resolution_y = 1920, 820
w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); sc.world = w
try:
    w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.34, 0.37, 0.4, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
except Exception: pass
for o in sc.objects:
    if o.type == 'LIGHT': o.data.energy = 3.5; o.rotation_euler = (math.radians(55), 0, math.radians(-35))
fd = bpy.data.lights.new("Fill", 'AREA'); fd.energy = 900; fd.size = 8; fl = bpy.data.objects.new("Fill", fd); sc.collection.objects.link(fl); fl.location = (5, -6, 4); fl.rotation_euler = (math.radians(55), 0, 0)
bpy.ops.mesh.primitive_plane_add(size=40, location=(5, 0, 0)); g = bpy.context.active_object
gm = bpy.data.materials.new("Floor"); gm.diffuse_color = (0.2, 0.2, 0.21, 1)
try:
    gm.use_nodes = True; gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.2, 0.2, 0.21, 1)
except Exception: pass
g.data.materials.append(gm)
cam = sc.camera; cam.location = (5, -14.0, 1.4); cam.rotation_euler = (math.radians(87), 0, 0); cam.data.lens = 34
sc.render.filepath = os.path.join(out, "armor_tiers_lineup.png"); bpy.ops.render.render(write_still=True); print("RENDERED lineup")
sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
for name, x in (("armor_tiers_close_1_3", 2.0), ("armor_tiers_close_4_6", 8.0)):
    cam.location = (x + 1.1, -5.4, 1.55); cam.rotation_euler = (math.radians(86), 0, math.radians(11)); cam.data.lens = 40
    sc.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True); print("RENDERED", name)

cam.location = (10.62, -2.0, 0.62); cam.rotation_euler = (math.radians(88), 0, math.radians(-6)); cam.data.lens = 50
sc.render.resolution_x, sc.render.resolution_y = 1000, 1000
sc.render.filepath = os.path.join(out, 'armor_shield_6_close.png'); bpy.ops.render.render(write_still=True); print('RENDERED shield6')
