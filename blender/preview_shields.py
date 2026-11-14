# Renders the FunFant Viking shield with each of its 9 painted texture sets (front view) for picking per-tier designs.
import bpy, sys, os, math, importlib.util
OUT = sys.argv[sys.argv.index("--") + 1]; here = os.path.dirname(os.path.abspath(__file__))
s = importlib.util.spec_from_file_location("wg", os.path.join(here, "warrior_gear.py")); WG = importlib.util.module_from_spec(s); s.loader.exec_module(WG)
bpy.ops.wm.read_homefile(use_empty=True)
D = os.path.join(WG.LIB, "Viking_Shields_FunFant", "Viking Shields")
sh = WG.import_prop(os.path.join(D, "models", "shield.fbx"), bpy.data.materials.new("tmp"), 0.85)
print("WIDTHS", WG.end_widths(sh, 1))
sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x = sc.render.resolution_y = 400
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN')); sun.data.energy = 3; sun.rotation_euler = (math.radians(60), 0, math.radians(-20)); sc.collection.objects.link(sun)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.type = 'ORTHO'; cam.data.ortho_scale = 0.95
for side, y in (("front", -2), ("back", 2)):
    cam.location = (0, y, 0); cam.rotation_euler = (math.radians(90), 0, 0 if y < 0 else math.pi); sun.rotation_euler = (math.radians(60), 0, math.radians(-20 if y < 0 else 160))
    for i in range(1, 10):
        T = os.path.join(D, "textures", "shield%d_" % i)
        m = WG.pbr_material("SC_Shield%d" % i, T + "diffuse.png", T + "normal.png", unity_metal_smooth=T + "metallic.png", rough_range=(0.3, 0.85))
        sh.data.materials[0] = m; sc.render.filepath = os.path.join(OUT, "shield%d_%s.png" % (i, side)); bpy.ops.render.render(write_still=True)

print("DONE")
