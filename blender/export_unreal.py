"""
Export Shattered Lands assets for Unreal Engine 5.

    blender --background --python export_unreal.py -- <models_dir> <out_dir> <part>
    part: viking | english | vikingtiers | terrain

Writes FBX (metres -> Unreal cm via unit scale, -Y forward / Z up, textures embedded) plus a
16-bit terrain heightmap. One part per Blender run, because each part opens its own .blend file.
"""
import bpy, sys, os, json, math
args = sys.argv[sys.argv.index("--") + 1:]; MD, OUT, PART = args[0], args[1], args[2]


def fbx(path, objects, anim=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects: o.hide_set(False); o.hide_render = False; o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'}, apply_unit_scale=True,
                             apply_scale_options='FBX_SCALE_ALL', axis_forward='-Y', axis_up='Z', use_mesh_modifiers=True,
                             mesh_smooth_type='FACE', use_tspace=True, add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
                             use_armature_deform_only=True, bake_anim=anim, bake_anim_use_all_actions=anim, bake_anim_use_nla_strips=False,
                             bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, path_mode='COPY', embed_textures=True)
    print("EXPORTED", os.path.relpath(path, OUT), len(objects), "objects", os.path.getsize(path) // 1024, "KB")


def open_blend(name):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(MD, name))


def place_at_origin(objs, x0):
    """Move a lineup member to the world origin (roots only; children follow)."""
    for o in objs:
        if o.parent is None or o.parent not in objs: o.location.x -= x0


if PART == "viking":
    # skinned MakeHuman Viking + idle/walk/guard/over/diag clips -> one Skeletal Mesh with Anim Sequences
    open_blend("viking_anim.blend")
    rig = bpy.data.objects["VikingRig"]; rig.name = "Armature"          # "Armature" avoids an extra root bone in Unreal
    for a in bpy.data.actions: a.use_fake_user = True
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and (o.parent == rig or any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers))
              and not o.hide_render and o.name not in ("Teeth",)]
    for o in meshes:                                                     # rigid props (sword/shield) bound to one bone already
        if o.parent != rig: o.parent = rig
    print("CLIPS", [a.name for a in bpy.data.actions], "MESHES", [o.name for o in meshes])
    fbx(os.path.join(OUT, "Characters", "Viking", "SK_Viking_Warrior.fbx"), [rig] + meshes, anim=True)

elif PART == "english":
    open_blend("english_soldiers_tiers.blend")
    for i in range(1, 7):
        sol = bpy.data.objects.get("Tier %d Soldier" % i)
        if sol is None: continue
        objs = [sol] + [c for c in sol.children_recursive if c.type == 'MESH']
        x0 = sol.location.x; sol.location.x = 0.0
        fbx(os.path.join(OUT, "Characters", "English", "SM_English_Tier%d.fbx" % i), objs)
        sol.location.x = x0

elif PART == "vikingtiers":
    open_blend("viking_armor_tiers.blend")
    for coll in sorted((c for c in bpy.data.collections if c.name.startswith("Tier ")), key=lambda c: c.name):
        i = int(coll.name.split()[1]); objs = [o for o in coll.all_objects if o.type == 'MESH']
        x0 = (i - 1) * 2.0
        for o in objs: o.location.x -= x0
        fbx(os.path.join(OUT, "Characters", "VikingTiers", "SM_Viking_Tier%d.fbx" % i), objs)
        for o in objs: o.location.x += x0
    # store/scanned materials (SC_*): record their source texture sets so Unreal can rebuild them faithfully
    import ast
    sc = {m.name: ast.literal_eval(m["sl_maps"]) for m in bpy.data.materials if m.name.startswith("SC_") and "sl_maps" in m}
    json.dump(sc, open(os.path.join(OUT, "Characters", "VikingTiers", "store_materials.json"), "w"), indent=1)
    print("STORE_MATERIALS", len(sc))

elif PART == "terrain":
    open_blend("terrain_patch.blend")
    ter = bpy.data.objects["TerrainPatch"]
    for o in bpy.data.objects:                                           # scatter instances are not part of the ground mesh
        if o != ter: o.hide_set(True)
    for ps in list(ter.modifiers):
        if ps.type == 'PARTICLE_SYSTEM': ps.show_viewport = False
    fbx(os.path.join(OUT, "Terrain", "SM_TerrainPatch_20m.fbx"), [ter])
    # 16-bit heightmap of the 20 m patch for a Landscape (505 x 505 = Unreal's 8x63-quad section layout + 1)
    dg = bpy.context.evaluated_depsgraph_get(); ev = ter.evaluated_get(dg)
    from mathutils.bvhtree import BVHTree
    from mathutils import Vector
    me = ev.to_mesh(); bvh = BVHTree.FromPolygons([ter.matrix_world @ v.co for v in me.vertices], [p.vertices[:] for p in me.polygons]); ev.to_mesh_clear()
    N, HALF = 505, 10.0; hs = []
    for j in range(N):
        for i in range(N):
            x, y = -HALF + 2 * HALF * i / (N - 1), HALF - 2 * HALF * j / (N - 1)
            hit = bvh.ray_cast(Vector((x, y, 50.0)), Vector((0, 0, -1)))
            hs.append(hit[0].z if hit[0] is not None else 0.0)
    lo, hi = min(hs), max(hs); rng = max(hi - lo, 1e-6)
    img = bpy.data.images.new("Height", N, N, float_buffer=True, is_data=True)
    px = []
    for j in range(N - 1, -1, -1):                                       # Blender images are bottom-up
        for i in range(N):
            v = (hs[j * N + i] - lo) / rng; px += [v, v, v, 1.0]
    img.pixels = px
    path = os.path.join(OUT, "Terrain", "T_TerrainPatch_Height_505.png")
    s = bpy.context.scene.render.image_settings; s.file_format = 'PNG'; s.color_mode = 'BW'; s.color_depth = '16'
    img.save_render(path)
    # Unreal Landscape scale: X/Y = cm per quad; Z = (range_cm / 512) because 16-bit spans +/-256 units at Z scale 100
    meta = {"size_m": 2 * HALF, "resolution": N, "height_min_m": lo, "height_max_m": hi,
            "unreal_scale_xy": round(2 * HALF * 100 / (N - 1), 4), "unreal_scale_z": round(rng * 100 / 512 * 100, 4)}
    json.dump(meta, open(os.path.join(OUT, "Terrain", "T_TerrainPatch_Height_505.json"), "w"), indent=1)
    print("HEIGHTMAP", path, meta)
