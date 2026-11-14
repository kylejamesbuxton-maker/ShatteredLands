"""
Renders a quick preview of each FBX/OBJ (front + 3/4 views side by side), auto-hooking the pack's textures by name.
    blender --background --python preview_assets.py -- <out_dir> <model1> [<model2> ...]
Prints MESHINFO lines (vertex count, size in metres, materials, armature) for each model.
"""
import bpy, sys, os, math
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]; OUT, MODELS = args[0], args[1:]
os.makedirs(OUT, exist_ok=True)


def hook_textures(folder):
    """Find <material>-ish textures in the pack and wire basecolor/normal/roughness/metallic where missing."""
    texdir = [os.path.join(r, f) for r, _, fs in os.walk(folder) for f in fs if f.lower().endswith((".png", ".tga", ".jpg", ".jpeg", ".tif", ".tiff"))]
    for m in bpy.data.materials:
        if not m.node_tree: continue
        bs = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not bs or bs.inputs["Base Color"].is_linked: continue
        key = m.name.lower().split(".")[0].replace("mat_", "").replace("_mat", "").replace("m_", "")
        cands = [t for t in texdir if key[:5] in os.path.basename(t).lower()] or texdir
        def pick(words):
            for t in cands:
                b = os.path.basename(t).lower()
                if any(w in b for w in words): return t
        for words, sock, cs in ((("albedo", "basecolor", "base_color", "diffuse", "_d.", "color", "_bc"), "Base Color", "sRGB"),
                                (("normal", "_n.", "nrm"), "Normal", "Non-Color"), (("rough",), "Roughness", "Non-Color"), (("metal",), "Metallic", "Non-Color")):
            t = pick(words)
            if not t: continue
            tx = m.node_tree.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(t, check_existing=True); tx.image.colorspace_settings.name = cs
            if sock == "Normal":
                nm = m.node_tree.nodes.new('ShaderNodeNormalMap'); m.node_tree.links.new(tx.outputs[0], nm.inputs["Color"]); m.node_tree.links.new(nm.outputs[0], bs.inputs["Normal"])
            else: m.node_tree.links.new(tx.outputs[0], bs.inputs[sock])


for path in MODELS:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fbx": bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=path)
    hook_textures(os.path.dirname(os.path.dirname(path)))
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    if not meshes: print("MESHINFO", path, "no meshes"); continue
    dg = bpy.context.evaluated_depsgraph_get()
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)]); size = hi - lo; ctr = (lo + hi) / 2
    print("MESHINFO", os.path.basename(path), "verts", sum(len(o.data.vertices) for o in meshes), "size_m", tuple(round(s, 3) for s in size),
          "materials", sorted({s.material.name for o in meshes for s in o.material_slots if s.material}),
          "armature", any(o.type == 'ARMATURE' for o in bpy.data.objects), "anims", len(bpy.data.actions))
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x, sc.render.resolution_y = 1000, 700; sc.render.film_transparent = False
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    for nm, rot, e in (("Key", (math.radians(50), 0, math.radians(-35)), 3.5), ("Fill", (math.radians(60), 0, math.radians(140)), 1.2)):
        L = bpy.data.objects.new(nm, bpy.data.lights.new(nm, 'SUN')); L.data.energy = e; L.rotation_euler = rot; sc.collection.objects.link(L)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = max(size) * 1.25
    base = os.path.splitext(os.path.basename(path))[0]
    for tag, d in (("front", Vector((0, -1, 0.15))), ("angle", Vector((0.75, -0.75, 0.3)))):
        # models arrive Y-up from Unity: look along whichever horizontal axis is thinner so the broad face shows
        if size.x < size.y * 0.5 and tag == "front": d = Vector((-1, 0, 0.15))
        cam.location = ctr + d.normalized() * max(size) * 3; cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, "%s_%s.png" % (base, tag)); bpy.ops.render.render(write_still=True)
    print("RENDERED", base)
