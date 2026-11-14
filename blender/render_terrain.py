import bpy, sys, os, math
out_dir = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "terrain_patch.blend"))
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'; sc.render.resolution_x, sc.render.resolution_y = 1280, 720
try:
    sc.eevee.use_shadows = True; sc.eevee.use_raytracing = True; sc.eevee.taa_render_samples = 64
except Exception: pass
w = bpy.data.worlds.new("Sky"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.55, 0.6, 0.66, 1); bg.inputs[1].default_value = 0.6
sd = bpy.data.lights.new("Sun", 'SUN'); sd.energy = 4.0; sd.angle = math.radians(1.2); sd.color = (1.0, 0.92, 0.8)
sun = bpy.data.objects.new("Sun", sd); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(72), 0, math.radians(-125))
cd = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
tg = bpy.data.objects.new("T", None); sc.collection.objects.link(tg)
tc = cam.constraints.new('TRACK_TO'); tc.target = tg; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast' if 'AgX - Medium High Contrast' in [i.identifier for i in sc.view_settings.bl_rna.properties['look'].enum_items] else 'None'
for name, loc, tgt, lens in (("terrain_lowangle", (3.2, -9.8, 1.25), (-0.6, 1.0, 0.0), 30),
                             ("terrain_ruts_close", (1.2, -3.6, 0.75), (0.2, -0.8, -0.05), 35),
                             ("terrain_overview", (9.5, -11.5, 9.0), (0, 0, 0), 32)):
    cam.location = loc; tg.location = tgt; cd.lens = lens
    sc.render.filepath = os.path.join(out_dir, name + ".png"); bpy.ops.render.render(write_still=True); print("RENDERED", name)
