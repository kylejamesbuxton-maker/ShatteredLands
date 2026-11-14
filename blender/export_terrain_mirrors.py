"""
Exports mirrored copies of the 20 m battlefield patch (X, Y and XY flips) as real geometry with corrected normals,
so Unreal can tile the ground seamlessly without negative actor scale (which breaks normal-map lighting).
    blender --background --python export_terrain_mirrors.py -- <models_dir> <out_dir>
"""
import bpy, sys, os
args = sys.argv[sys.argv.index("--") + 1:]; MD, OUT = args[0], args[1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(MD, "terrain_patch.blend"))
ter = bpy.data.objects["TerrainPatch"]
for m in list(ter.modifiers):
    if m.type == 'PARTICLE_SYSTEM': m.show_viewport = False
dg = bpy.context.evaluated_depsgraph_get()
base = bpy.data.meshes.new_from_object(ter.evaluated_get(dg)); base.transform(ter.matrix_world)
for o in list(bpy.data.objects): o.hide_set(True)
os.makedirs(OUT, exist_ok=True)
for tag, sx, sy in (("MX", -1, 1), ("MY", 1, -1), ("MXY", -1, -1)):
    me = base.copy(); me.name = "SM_TerrainPatch_20m_" + tag
    import mathutils
    me.transform(mathutils.Matrix.Diagonal((sx, sy, 1, 1)))
    if sx * sy < 0: me.flip_normals()                       # one flip turns faces inside out; put them back
    ob = bpy.data.objects.new(me.name, me); bpy.context.scene.collection.objects.link(ob)
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, me.name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
                             axis_forward='-Y', axis_up='Z', mesh_smooth_type='FACE', use_tspace=True, path_mode='COPY', embed_textures=False)
    print("EXPORTED", path)
