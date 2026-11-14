# Test: open the Viking tiers scene, run refine_viking_assets.py twice (idempotence), report, Cycles render.
import bpy, sys, os, runpy, time
args = sys.argv[sys.argv.index("--") + 1:]; blend, script, out = args[0], args[1], args[2]
samples = int(args[3]) if len(args) > 3 else 24
bpy.ops.wm.open_mainfile(filepath=blend)
t = time.time(); runpy.run_path(script, run_name="__main__"); print("RUN1 %.1fs" % (time.time() - t))
mods_after_1 = sum(len(o.modifiers) for o in bpy.data.objects if o.type == 'MESH')
runpy.run_path(script, run_name="__main__")
mods_after_2 = sum(len(o.modifiers) for o in bpy.data.objects if o.type == 'MESH')
lights = [o.name for o in bpy.data.objects if o.type == 'LIGHT' and o.name.startswith("Refine")]
cams = [o.name for o in bpy.data.objects if o.type == 'CAMERA' and o.name.startswith("Refine")]
print("IDEMPOTENT modifiers run1=%d run2=%d lights=%s cams=%s" % (mods_after_1, mods_after_2, lights, cams))
kinds = {}
for o in bpy.data.objects:
    for m in o.modifiers: kinds[m.type] = kinds.get(m.type, 0) + 1
print("MODIFIERS", kinds)
print("MATERIAL_NODES", {m.name: len(m.node_tree.nodes) for m in bpy.data.materials if m.node_tree and m.get("Refine_done")})
# floor for the test render only
me = bpy.data.meshes.new("Floor"); me.from_pydata([(-20, -20, 0), (30, -20, 0), (30, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
fl = bpy.data.objects.new("Floor", me); bpy.context.scene.collection.objects.link(fl)
fm = bpy.data.materials.new("Floor"); fm.use_nodes = True; fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.085, 0.08, 1); fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8; me.materials.append(fm)
sc = bpy.context.scene; sc.cycles.samples = samples; sc.render.resolution_x, sc.render.resolution_y = 1920, 820
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "viking_armor_refined.blend"))
for name, setup in (("refined_lineup", None), ("refined_close", "close")):
    if setup == "close":
        cam = sc.camera; c = bpy.data.objects
        cam.location = (11.0, -4.6, 1.25); cam.rotation_euler = (1.53, 0, 0.18); cam.data.dof.focus_distance = 4.7; cam.data.dof.focus_object = None
        sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
    t = time.time(); sc.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True)
    print("RENDERED", name, "%.0fs" % (time.time() - t))