import bpy, sys, os, math
args = sys.argv[sys.argv.index("--") + 1:]
blend, out, mode = args[0], args[1], (args[2] if len(args) > 2 else "full")
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
hide = set(args[3].split(",")) if len(args) > 3 and args[3] else set()
for o in scene.objects:
    if o.name in hide: o.hide_render = True
try:
    scene.render.engine = 'BLENDER_EEVEE'
except Exception:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x, scene.render.resolution_y = (800, 1000) if mode == "full" else (800, 800)
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.42, 0.47, 0.5, 1); bg.inputs[1].default_value = 0.7
sun_d = bpy.data.lights.new("Sun", 'SUN'); sun_d.energy = 3.2; sun = bpy.data.objects.new("Sun", sun_d); scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
fill_d = bpy.data.lights.new("Fill", 'AREA'); fill_d.energy = 120; fill_d.size = 3; fill = bpy.data.objects.new("Fill", fill_d); scene.collection.objects.link(fill)
fill.location = (-2.5, -2.0, 1.6); fill.rotation_euler = (math.radians(70), 0, math.radians(-50))
cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d); scene.collection.objects.link(cam); scene.camera = cam
tgt = bpy.data.objects.new("T", None); scene.collection.objects.link(tgt)
if mode == "full":
    cam.location = (1.6, -4.2, 1.25); tgt.location = (0, 0, 0.95); cam_d.lens = 55
else:  # face close-up
    cam.location = (0.32, -0.75, 1.72); tgt.location = (0, -0.04, 1.66); cam_d.lens = 70
tc = cam.constraints.new('TRACK_TO'); tc.target = tgt; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("RENDERED", out)
