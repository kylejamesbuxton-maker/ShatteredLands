# Same tall building twice with a UV-grid image: left = Generated coordinates (flat projection, stretches),
# right = the box-mapped material (Object coords -> Mapping -> Image Texture with BOX projection, blend 0.2).
import bpy, bmesh, sys, os, math, runpy
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1]; here = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
ns = runpy.run_path(os.path.join(here, "box_mapped_material.py"), run_name="lib")
sc = bpy.context.scene
img = bpy.data.images.new("Grid", 1024, 1024); img.generated_type = 'UV_GRID'

def building(name, x0):
    bm = bmesh.new()
    for size, off in (((4, 3, 7), (0, 0, 3.5)), ((2.5, 3.2, 2), (0, 0, 8)), ((1.2, 1.2, 4), (2.6, 0.6, 2))):   # tower, roof block, side wing
        v = bmesh.ops.create_cube(bm, size=1)["verts"]
        bmesh.ops.scale(bm, vec=Vector(size), verts=v); bmesh.ops.translate(bm, vec=Vector(off), verts=v)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); ob.location.x = x0; sc.collection.objects.link(ob); return ob

flat = bpy.data.materials.new("Generated (flat)"); flat.use_nodes = True; nt = flat.node_tree
tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img; tc = nt.nodes.new('ShaderNodeTexCoord')
nt.links.new(tc.outputs['Generated'], tx.inputs['Vector']); nt.links.new(tx.outputs['Color'], nt.nodes["Principled BSDF"].inputs['Base Color'])
box = ns["create_box_mapped_material"](img, tile=0.5)
building("A", -4).data.materials.append(flat); building("B", 4).data.materials.append(box)

g = bpy.data.meshes.new("G"); g.from_pydata([(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], [], [(0, 1, 2, 3)])
sc.collection.objects.link(bpy.data.objects.new("Ground", g))
sc.render.engine = 'CYCLES'; sc.cycles.samples = 32; sc.render.resolution_x, sc.render.resolution_y = 1500, 900
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.65, 0.72, 1)
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN')); sun.data.energy = 3.5; sun.rotation_euler = (math.radians(55), 0, math.radians(-40)); sc.collection.objects.link(sun)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (9, -20, 9); cam.rotation_euler = (Vector((0, 0, 4)) - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = 35
sc.render.filepath = os.path.join(out, "box_mapping_test.png"); bpy.ops.render.render(write_still=True); print("RENDERED")
