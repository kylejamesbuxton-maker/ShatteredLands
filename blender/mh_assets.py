"""
MakeHuman 1.x asset bridge for MPFB characters.

MakeHuman Community 1.3 installs its system assets (eyebrows, eyelashes, eyes, teeth, tongue, hair, proxies,
clothes) only in compiled form: <name>.npz (mesh) + <name>.mhpxy (fitting data). MPFB reads the source .mhclo
format, so this module fits the compiled assets onto an MPFB basemesh directly:

    vertex = sum_k w_k * base[ref_k]  +  offset * scale        (MakeHuman's proxy fitting)

and copies skeleton weights from the same reference vertices, so assets deform with the rig.
Skins (.mhmat + textures) are handed to MPFB's own HumanService.set_character_skin.

All MakeHuman system assets used here are CC0 (stated in each asset's licence block).
"""
import bpy, bmesh, os
import numpy as np
from mathutils import Vector

MH_DATA = os.path.join(os.environ.get("LOCALAPPDATA", ""), "makehuman-community", "makehuman", "data")


def _s(arr):
    return b"".join(arr.tolist()).decode("utf-8", "replace") if arr.size else ""


def _strings(z, key):
    s, idx = _s(z[key + "_str"]), z[key + "_idx"].tolist()
    return [s[a:b] for a, b in zip(idx, idx[1:] + [len(s)])] if idx else []


def read_mhmat(path):
    """Minimal .mhmat parser -> dict of keys (textures resolved to absolute paths)."""
    out, base = {}, os.path.dirname(path)
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        k, _, v = line.partition(" ")
        if k.endswith("Texture"):
            p = os.path.normpath(os.path.join(base, v))
            if not os.path.exists(p): p = os.path.normpath(os.path.join(MH_DATA, "..", v))
            out[k] = p
        else:
            out[k] = v
    return out


def base_coords_mh(basemesh):
    """Evaluated basemesh vertices converted back to MakeHuman space (decimetres, Y up, Z forward)."""
    saved = [(m, m.show_viewport) for m in basemesh.modifiers]          # masks/armature would renumber or move verts
    for m, _ in saved: m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get(); dg.update(); ev = basemesh.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float64); me.vertices.foreach_get("co", co); ev.to_mesh_clear()
    for m, state in saved: m.show_viewport = state
    if len(co) // 3 != len(basemesh.data.vertices): raise RuntimeError("basemesh vertex count changed; cannot fit MakeHuman assets")
    co = co.reshape(-1, 3)
    scale = basemesh.get("scale_factor", None) or 0.1
    mh = np.stack([co[:, 0], co[:, 2], -co[:, 1]], axis=1) / scale
    return mh, scale


def fit_asset(kind, name, basemesh, rig=None, material=None, obj_name=None, z_bias=0.0, tint=None):
    """Fit compiled MakeHuman asset data/<kind>/<name>/<name>.(npz|mhpxy) onto `basemesh`."""
    folder = os.path.join(MH_DATA, kind, name)
    px = np.load(os.path.join(folder, name + ".mhpxy"), allow_pickle=False)
    mesh_file = _s(px["obj_file"]).replace(".obj", ".npz") or name + ".npz"
    mz = np.load(os.path.join(folder, os.path.basename(mesh_file)), allow_pickle=False)
    base, scale = base_coords_mh(basemesh)
    ref, w = px["ref_vIdxs"].astype(np.int64), px["weights"].astype(np.float64)
    if ref.ndim == 1: ref = ref[:, None]
    if w.ndim == 1: w = w[:, None]
    if ref.shape[1] < 3:                                                      # exact-vertex proxies: pad to 3 refs
        ref = np.concatenate([ref, np.repeat(ref[:, :1], 3 - ref.shape[1], axis=1)], axis=1)
        w = np.concatenate([w, np.zeros((len(w), 3 - w.shape[1]))], axis=1)
    off = px["offsets"].astype(np.float64) if "offsets" in px.files else np.zeros((len(ref), 3))
    pos = (base[ref] * w[:, :, None]).sum(axis=1)
    ts, ti = px["tmat_scale"].astype(np.float64), px["tmat_scale_idx"].tolist()
    if len(ti) == 6 and np.all(ts > 0):                                       # per-axis offset scaling
        sfac = np.array([abs(base[ti[2 * a], a] - base[ti[2 * a + 1], a]) / ts[a] for a in range(3)])
        pos += off * sfac
    else:
        pos += off
    if z_bias: pos[:, 2] += z_bias
    blender = np.stack([pos[:, 0], -pos[:, 2], pos[:, 1]], axis=1) * scale    # back to Blender metres, Z up
    # faces (quads, tris marked by repeated last index) and UVs
    fv, fuv, tc = mz["fvert"].tolist(), mz["fuvs"].tolist(), mz["texco"]
    me = bpy.data.meshes.new(obj_name or name)
    faces = [tuple(dict.fromkeys(f)) if len(set(f)) < 4 else tuple(f) for f in fv]
    me.from_pydata(blender.tolist(), [], faces); me.update()
    uv = me.uv_layers.new(name="UVMap")
    li = 0
    for f_i, f in enumerate(faces):
        for c in range(len(f)):
            u, v = tc[fuv[f_i][c]]; uv.data[li].uv = (float(u), float(v)); li += 1
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(obj_name or name, me); bpy.context.collection.objects.link(ob)
    # skeleton weights interpolated from the reference body vertices
    if rig is not None:
        bones = {b.name for b in rig.data.bones}; gidx = {g.index: g.name for g in basemesh.vertex_groups if g.name in bones}
        bw = {}
        bverts = basemesh.data.vertices
        for vi in range(len(ref)):
            acc = {}
            for k in range(3):
                for g in bverts[int(ref[vi, k])].groups:
                    n = gidx.get(g.group)
                    if n: acc[n] = acc.get(n, 0.0) + g.weight * float(w[vi, k])
            for n, val in acc.items():
                if val > 0.001: bw.setdefault(n, []).append((vi, val))
        for n, items in bw.items():
            grp = ob.vertex_groups.new(name=n)
            for vi, val in items: grp.add([vi], val, 'REPLACE')
        ob.parent = rig; md = ob.modifiers.new("Armature", 'ARMATURE'); md.object = rig
    if material is None:
        mm = os.path.join(folder, _s(px["material_file"]) or name + ".mhmat")
        if os.path.exists(mm): material = material_from_mhmat(mm, name, roughness=0.45 if kind == "teeth" else 0.6, tint=tint)
    if material is not None: me.materials.append(material)
    return ob


def material_from_mhmat(path, name=None, roughness=0.6, alpha_clip=True, normal_strength=1.0, tint=None):
    """Principled material from a .mhmat: diffuse (with alpha for hair/brows/lashes) + optional normal map.
    tint=(r,g,b) multiplies the diffuse texture (MakeHuman hair textures are near-neutral; colour came from litspheres)."""
    d = read_mhmat(path); m = bpy.data.materials.new(name or d.get("name", os.path.basename(path)))
    if "normalmapTexture" not in d and "diffuseTexture" in d:                  # sibling *_normal.png not always referenced
        guess = d["diffuseTexture"].replace("_diffuse", "_normal")
        if guess != d["diffuseTexture"] and os.path.exists(guess): d["normalmapTexture"] = guess
    if hasattr(m, "use_nodes"): m.use_nodes = True
    nt = m.node_tree; bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs["Roughness"].default_value = roughness
    if "diffuseTexture" in d and os.path.exists(d["diffuseTexture"]):
        tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(d["diffuseTexture"], check_existing=True)
        col = tx.outputs["Color"]
        if tint is not None:
            mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
            sk = {s.identifier: s for s in mx.inputs}; ok = {s.identifier: s for s in mx.outputs}
            sk["Factor_Float"].default_value = 1.0
            nt.links.new(col, sk["A_Color"]); sk["B_Color"].default_value = (*tint, 1.0); col = ok["Result_Color"]
        nt.links.new(col, bs.inputs["Base Color"])
        if d.get("transparent", "False") == "True" or alpha_clip:
            nt.links.new(tx.outputs["Alpha"], bs.inputs["Alpha"])
            for attr, val in (("surface_render_method", 'DITHERED'), ("blend_method", 'HASHED')):
                if hasattr(m, attr):
                    try: setattr(m, attr, val)
                    except Exception: pass
    if "normalmapTexture" in d and os.path.exists(d["normalmapTexture"]):
        nx = nt.nodes.new('ShaderNodeTexImage'); nx.image = bpy.data.images.load(d["normalmapTexture"], check_existing=True)
        nx.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs["Strength"].default_value = normal_strength
        nt.links.new(nx.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
    return m


def apply_skin(basemesh, skin_name, variant=None):
    """MakeHuman skin via MPFB's own skin system (SSS, textures)."""
    from bl_ext.blender_org.mpfb.services.humanservice import HumanService
    folder = os.path.join(MH_DATA, "skins", skin_name)
    mhmat = os.path.join(folder, (variant or skin_name) + ".mhmat")
    HumanService.set_character_skin(mhmat, basemesh, skin_type="ENHANCED_SSS")
    return mhmat


def list_assets(kind):
    p = os.path.join(MH_DATA, kind)
    return sorted(d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d)) and os.path.exists(os.path.join(p, d, d + ".mhpxy"))) if os.path.isdir(p) else []
