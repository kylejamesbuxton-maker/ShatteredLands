# Test: refit the Unity warrior's historical clothing onto a posed MakeHuman man and render front/side/close views.
#   blender --background --python test_warrior_fit.py -- <out_dir>
import bpy, sys, os, math, importlib.util
from mathutils import Vector
OUT = sys.argv[sys.argv.index("--") + 1]; here = os.path.dirname(os.path.abspath(__file__))
def load(n):
    s = importlib.util.spec_from_file_location(n, os.path.join(here, n + ".py")); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
bpy.ops.wm.read_homefile(use_empty=True)
MHC = load("mh_character"); WG = load("warrior_gear")
ch = MHC.MHCharacter({"gender": 1.0, "age": 0.48, "muscle": 0.75, "weight": 0.55, "proportions": 0.6, "height": 0.5, "cupsize": 0.5, "firmness": 0.5,
                      "race": {"asian": 0.0, "caucasian": 1.0, "african": 0.0}}, skin="middleage_caucasian_male", name="Fit")
ch.fit_height(1.782, (0.0, -0.005))
SH, EL, WR = Vector((0.235, 0.0, 1.415)), Vector((0.295, 0.0, 1.135)), Vector((0.325, -0.03, 0.875))   # mannequin hang pose directions
for s, sx in (("L", 1), ("R", -1)):
    m = lambda p: Vector((p.x * sx, p.y, p.z)); sh = ch.shoulder(s); Lu, Lf = ch.arm_lengths(s)
    el = sh + m(EL - SH).normalized() * Lu; wr = el + m(WR - EL).normalized() * Lf
    ch.aim_arm(s, el, wr); ch.curl_fingers(s, 0.35)
ch.add_face(eye="grey", hair=None, hair_tint=(0.2, 0.13, 0.07), beard="full")
body = ch.bake(show=("head", "neck", "hands"), hair=False, name="MH", neck_column=(1.43, 0.105, ch.joint("neck_01").y - 0.01))
gear = WG.WarriorGear(ch)
g = gear.fit(["Body", "Coat", "Belt_2", "Bag", "Fur", "Accessories"])
n1 = WG.push_out(g["Coat"], [g["Body"]], 0.004)
for k in ("Belt_2", "Bag", "Fur", "Accessories"):
    if k in g: print("PUSH", k, WG.push_out(g[k], [g["Coat"], g["Body"]], 0.003))
print("FIT", {k: len(o.data.vertices) for k, o in g.items()}, "coat pushed", n1)
gear.remove(); ch.remove_rig()
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 48; sc.view_settings.view_transform = "AgX"
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.48, 0.52, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN')); sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), 0, math.radians(-30)); sc.collection.objects.link(sun)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
for nm, loc, tgt, lens, res in (("fit_front", (0.0, -4.2, 1.0), (0, 0, 0.95), 50, (700, 1000)), ("fit_angle", (2.6, -3.2, 1.2), (0, 0, 0.95), 50, (700, 1000)),
                                ("fit_close", (0.35, -1.25, 1.35), (0, 0, 1.22), 50, (900, 900))):
    cam.location = loc; cam.data.lens = lens; cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.filepath = os.path.join(OUT, nm + ".png"); bpy.ops.render.render(write_still=True); print("RENDERED", nm)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "warrior_fit_test.blend"))
