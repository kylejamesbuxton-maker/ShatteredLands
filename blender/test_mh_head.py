# Test: MPFB human + MakeHuman skin, eyes, eyebrows, eyelashes, teeth, hair (via mh_assets) -> Cycles head/body renders.
import bpy, sys, os, math, importlib.util, addon_utils
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("mh_assets", os.path.join(here, "mh_assets.py")); mh = importlib.util.module_from_spec(spec); spec.loader.exec_module(mh)
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)
from bl_ext.blender_org.mpfb.services.humanservice import HumanService
print("AVAILABLE", {k: mh.list_assets(k) for k in ("eyebrows", "eyelashes", "eyes", "hair", "teeth", "tongue")})
macro = {"gender": 1.0, "age": 0.55, "muscle": 0.72, "weight": 0.55, "proportions": 0.6, "height": 0.58, "cupsize": 0.5, "firmness": 0.5,
         "race": {"asian": 0.0, "caucasian": 1.0, "african": 0.0}}
body = HumanService.create_human(macro_detail_dict=macro); rig = HumanService.add_builtin_rig(body, "game_engine")
bpy.context.view_layer.objects.active = body
if body.data.shape_keys: bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
skin = mh.apply_skin(body, "middleage_caucasian_male"); print("SKIN", skin, [s.material.name for s in body.material_slots if s.material])
eye_mat = mh.material_from_mhmat(os.path.join(mh.MH_DATA, "eyes", "materials", "brown.mhmat"), "Eyes Brown", roughness=0.1, alpha_clip=False, tint=(0.62, 0.6, 0.62))
parts = {"eyes": mh.fit_asset("eyes", "high-poly", body, rig, material=eye_mat, obj_name="Eyes"),
         "eyebrows": mh.fit_asset("eyebrows", "eyebrow003", body, rig, obj_name="Eyebrows", tint=(0.34, 0.24, 0.15)),
         "eyelashes": mh.fit_asset("eyelashes", "eyelashes01", body, rig, obj_name="Eyelashes", tint=(0.3, 0.22, 0.16)),
         "teeth": mh.fit_asset("teeth", "teeth_base", body, rig, obj_name="Teeth"),
         "hair": mh.fit_asset("hair", "short02", body, rig, obj_name="Hair", tint=(0.42, 0.29, 0.17))}
for k, o in parts.items():
    print("PART", k, len(o.data.vertices), "verts", len(o.vertex_groups), "bone groups", [m.name for m in o.data.materials])
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 64
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.32, 0.34, 0.37, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.3; sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
head = Vector((0, -0.02, 1.7))
for nm, loc, e, size in (("Key", (-0.8, -1.2, 2.2), 70, 0.8), ("Fill", (0.9, -1.0, 1.8), 18, 1.2), ("Rim", (0.3, 1.0, 2.1), 60, 0.7)):
    ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.size = size; ob = bpy.data.objects.new(nm, ld); sc.collection.objects.link(ob); ob.location = loc
    ob.rotation_euler = (head - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
cd = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
for nm, loc, tgt, lens, res in (("mh_head_front", (0.12, -0.75, 1.72), head, 85, (900, 1000)), ("mh_head_angle", (0.5, -0.55, 1.75), head, 85, (900, 1000)),
                                ("mh_body", (0.0, -4.0, 1.0), Vector((0, 0, 0.95)), 50, (800, 1100))):
    cd.lens = lens; cam.location = loc; cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(out, nm + ".png"); bpy.ops.render.render(write_still=True); print("RENDERED", nm)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "mh_test_head.blend"))
