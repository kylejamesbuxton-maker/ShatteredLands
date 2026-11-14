# Exports viking_anim.blend to a compact game format: viking.json (header) + viking.bin (binary)
# Coordinates converted Blender (x, y, z; -Y forward) -> three.js (x, z, -y; +Z forward). Units: metres.
import bpy, sys, os, json, struct, math
from mathutils import Matrix, Vector
mdir = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(mdir, "viking_anim.blend"))
rig = bpy.data.objects["VikingRig"]; bones = list(rig.data.bones); bidx = {b.name: i for i, b in enumerate(bones)}
CB = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1))); CBi = CB.inverted()
def conv(m): return CB @ m @ CBi
def tq(m):
    t, q, _ = m.decompose(); return [round(t.x, 5), round(t.y, 5), round(t.z, 5)], [q.x, q.y, q.z, q.w]
blob = bytearray()
def put(fmt, data):
    while len(blob) % 4: blob.append(0)
    off = len(blob); blob.extend(struct.pack("<%d%s" % (len(data), fmt), *data)); return off

# ---- skeleton (rest, local to parent)
B = []
for b in bones:
    loc = b.matrix_local if b.parent is None else b.parent.matrix_local.inverted() @ b.matrix_local
    t, q = tq(conv(loc)); B.append({"name": b.name, "parent": bidx[b.parent.name] if b.parent else -1, "t": t, "q": q})

# ---- meshes (rest pose, decimated). Vertices are split at UV seams so textures map cleanly.
DEC = {"Body": 0.55, "Clothes": 0.45, "TunicSkirt": 0.6, "Boots": 0.7, "Beard": 1.0, "Hair": 1.0, "Eyebrows": 1.0, "Eyelashes": 1.0,
       "Helmet": 0.55, "Mail": 0.5, "Eyes": 1.0, "Collar": 1.0, "Belt": 1.0, "Sword": 1.0, "Shield": 1.0}
TEX_SIZE = {"Body": (1024, 'JPEG'), "Hair": (512, 'PNG'), "Eyebrows": (256, 'PNG'), "Eyelashes": (128, 'PNG'), "Eyes": (256, 'PNG')}
WHITE_RGB = {"Eyebrows", "Eyelashes"}       # colour comes from the material (per-man hair colour); texture keeps only alpha
GREY_RGB = {"Hair"}                         # strand detail kept as normalised grey so any hair colour can tint it
BEARD_SHELLS = (0, 2, 4, 6)                         # of 8 built shells, the game keeps 4
def srgb_hex(c):
    f = lambda x: 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return "#%02x%02x%02x" % tuple(int(max(0, min(1, f(v))) * 255 + 0.5) for v in c[:3])
TEX = {}
def diffuse_image(m):
    if not m or not m.node_tree: return None
    def walk(tree):
        for n in tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image and "normal" not in n.image.name.lower() and "_spec" not in n.image.name.lower(): yield n.image
            if n.type == 'GROUP' and n.node_tree: yield from walk(n.node_tree)
    imgs = list(walk(m.node_tree)); pick = [i for i in imgs if "diffuse" in i.name.lower() or "eye" in i.name.lower()]
    return (pick or imgs or [None])[0]
def export_tex(img, part):
    size, fmt = TEX_SIZE[part]; key = part.lower()
    if key in TEX: return key
    cp = img.copy(); cp.scale(size, size)
    if part in WHITE_RGB or part in GREY_RGB:
        import numpy as np
        px = np.empty(size * size * 4, dtype=np.float32); cp.pixels.foreach_get(px); px = px.reshape(-1, 4)
        if part in WHITE_RGB: px[:, :3] = 1.0
        else:
            lum = px[:, :3] @ np.array([0.3, 0.55, 0.15], dtype=np.float32); op = px[:, 3] > 0.5
            ref = np.percentile(lum[op], 95) if op.any() else 1.0
            px[:, :3] = np.clip(lum / max(ref, 1e-3), 0, 1)[:, None] * 0.9 + 0.1
        cp.pixels.foreach_set(px.ravel())
    ext = "jpg" if fmt == 'JPEG' else "png"; path = os.path.join(mdir, "vktex_%s.%s" % (key, ext))
    sc = bpy.context.scene; s = sc.render.image_settings; s.file_format = fmt; s.color_mode = 'RGB' if fmt == 'JPEG' else 'RGBA'
    if fmt == 'JPEG': s.quality = 82
    else: s.compression = 100
    cp.save_render(path, scene=sc); bpy.data.images.remove(cp)
    TEX[key] = {"file": os.path.basename(path), "alpha": fmt == 'PNG'}; print("TEX", key, os.path.getsize(path), "bytes"); return key
parts = []
for name, ratio in DEC.items():
    ob = bpy.data.objects.get(name)
    if ob is None: continue
    for m in ob.modifiers:
        if m.type == 'ARMATURE': m.show_viewport = False
    dm = None
    if ratio < 1: dm = ob.modifiers.new("ExportDecimate", 'DECIMATE'); dm.ratio = ratio
    dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); me = ev.to_mesh()
    me.calc_loop_triangles()
    gname = {g.index: g.name for g in ob.vertex_groups}
    W = ob.matrix_world; N3 = W.to_3x3()
    shell = None
    if name == "Beard" and "shell" in me.attributes:
        sa = me.attributes["shell"].data; shell = [round(sa[i].value * 7) for i in range(len(me.vertices))]
    uvl = me.uv_layers.active.data if me.uv_layers.active else None
    # beard gets cylindrical UVs round the head so the game's strand texture runs downward
    hcy = sum(v.co.y for v in me.vertices) / max(1, len(me.vertices))
    remap, pos, nrm, sidx, swt, uvs = {}, [], [], [], [], []
    bymat = {}
    for tri in me.loop_triangles:
        mi = tri.material_index
        if shell is not None:
            ss = [shell[v] for v in tri.vertices]
            if ss[0] not in BEARD_SHELLS or len(set(ss)) > 1: continue
            mi = BEARD_SHELLS.index(ss[0])
        out = []
        for li in tri.loops:
            vi = me.loops[li].vertex_index; v = me.vertices[vi]
            if shell is not None:
                uv = (math.atan2(v.co.x, -(v.co.y - hcy - 0.06)) * 9.0, v.co.z * 14.0)
            else:
                uv = tuple(uvl[li].uv) if uvl else (0.0, 0.0)
            key = (vi, round(uv[0], 5), round(uv[1], 5))
            if key not in remap:
                remap[key] = len(remap)
                p = W @ v.co; n = (N3 @ v.normal).normalized()
                pos += [p.x, p.z, -p.y]; nrm += [max(-127, min(127, round(c * 127))) for c in (n.x, n.z, -n.y)]
                ws = sorted(((g.weight, bidx[gname[g.group]]) for g in v.groups if gname.get(g.group) in bidx and g.weight > 0.001), reverse=True)[:4]
                tot = sum(w for w, _ in ws) or 1.0; ws = ws + [(0.0, 0)] * (4 - len(ws))
                q = [round(w / tot * 255) for w, _ in ws]; q[0] += 255 - sum(q)
                swt += q; sidx += [i for _, i in ws]; uvs += [uv[0], uv[1]]
            out.append(remap[key])
        bymat.setdefault(mi, []).extend(out)
    nv = len(remap); idx, groups = [], []
    for mi in sorted(bymat):
        groups.append({"start": len(idx), "count": len(bymat[mi]), "mat": mi}); idx += bymat[mi]
    if shell is not None:
        mats = [{"name": "BeardShell%d" % k, "color": srgb_hex(ob.data.materials[0].diffuse_color), "metal": 0, "rough": 0.8, "shell": k} for k in range(len(BEARD_SHELLS))]
    else:
        mats = []
        for m in ob.data.materials:
            rec_m = {"name": m.name, "color": srgb_hex(m.diffuse_color), "metal": round(m.metallic, 2), "rough": round(m.roughness, 2)}
            img = diffuse_image(m) if name in TEX_SIZE else None
            if img is not None:
                rec_m["tex"] = export_tex(img, name)
                if name == "Eyes": rec_m["color"] = "#ffffff"
                if name == "Body": rec_m["color"] = "#ffe9dc"
            mats.append(rec_m)
    rec = {"name": name, "verts": nv, "tris": len(idx) // 3, "mats": mats, "groups": groups,
           "pos": put("f", pos), "nrm": put("b", nrm), "sidx": put("B", sidx), "swt": put("B", swt), "idx": put("H" if nv < 65536 else "I", idx), "idx32": nv >= 65536}
    rec["uv"] = put("f", uvs)
    parts.append(rec); ev.to_mesh_clear()
    if dm: ob.modifiers.remove(dm)
    for m in ob.modifiers:
        if m.type == 'ARMATURE': m.show_viewport = True
    print("PART", name, rec["verts"], "verts", rec["tris"], "tris", [x.get("tex") for x in mats])
# ---- animations: local bone rotations sampled at 15 fps; pelvis translation too
scene = bpy.context.scene; clips = []
STEP = 2  # 30 fps keys -> 15 fps samples
for act in bpy.data.actions:
    rig.animation_data.action = act
    f0, f1 = [int(round(x)) for x in act.frame_range]
    frames = list(range(f0, f1 + 1, STEP))
    if frames[-1] != f1: frames.append(f1)
    qs, ts = [], []
    for f in frames:
        scene.frame_set(f)
        for b in bones:
            pb = rig.pose.bones[b.name]
            loc = pb.matrix if b.parent is None else rig.pose.bones[b.parent.name].matrix.inverted() @ pb.matrix
            t, q = tq(conv(loc)); qs += q
            if b.name == "pelvis": ts += t
    clips.append({"name": act.name, "times": [(f - f0) / 30.0 for f in frames], "q": put("f", qs), "pelvisT": put("f", ts)})
    print("CLIP", act.name, len(frames), "samples")

hdr = {"bones": B, "parts": parts, "clips": clips, "tex": TEX, "bytes": len(blob), "height": round(max(v[1] for v in [[0, 0]]), 3)}
with open(os.path.join(mdir, "viking.bin"), "wb") as fh: fh.write(blob)
with open(os.path.join(mdir, "viking.json"), "w") as fh: json.dump(hdr, fh, separators=(",", ":"))
print("EXPORTED bytes", len(blob), "json", os.path.getsize(os.path.join(mdir, "viking.json")))
