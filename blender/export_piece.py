# Export one armour piece (by object-name prefix) from viking_armor_tiers.blend as a clean GLB for texturing services.
#   blender --background --python export_piece.py -- <blend> <name_prefix,...> <out.glb>
import bpy, sys, os
args = sys.argv[sys.argv.index("--") + 1:]; blend, prefixes, out = args[0], args[1].split(","), args[2]
bpy.ops.wm.open_mainfile(filepath=blend)
keep = [o for o in bpy.data.objects if o.type == 'MESH' and any(o.name.startswith(p) for p in prefixes)]
print("PIECES", [o.name for o in keep])
dg = bpy.context.evaluated_depsgraph_get()
new_objs = []
for o in keep:                                   # bake modifiers (mirror/solidify) + one smoothing level into a plain mesh
    sub = o.modifiers.new("Smooth", 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); o.modifiers.remove(sub)
    no = bpy.data.objects.new(o.name + "_export", me); no.matrix_world = o.matrix_world.copy()
    bpy.context.scene.collection.objects.link(no); new_objs.append(no)
# centre on the origin, sitting on the ground, real-world scale (metres)
from mathutils import Vector
pts = [no.matrix_world @ v.co for no in new_objs for v in no.data.vertices]
c = sum(pts, Vector()) / len(pts); zmin = min(p.z for p in pts)
for no in new_objs:
    no.matrix_world.translation -= Vector((c.x, c.y, zmin))
bpy.ops.object.select_all(action='DESELECT')
for no in new_objs: no.select_set(True)
bpy.context.view_layer.objects.active = new_objs[0]
if len(new_objs) > 1: bpy.ops.object.join()
ob = bpy.context.active_object; ob.name = os.path.splitext(os.path.basename(out))[0]
for p in ob.data.polygons: p.use_smooth = True
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_apply=True)
print("EXPORTED", out, len(ob.data.polygons), "faces", os.path.getsize(out), "bytes")
