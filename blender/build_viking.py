# Builds a clothed, rigged Viking warrior from an MPFB human. Run headless:
#   blender --background --python build_viking.py -- <out_dir>
import bpy, bmesh, sys, os, math, addon_utils
from mathutils import Vector
out_dir = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out_dir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)
from bl_ext.blender_org.mpfb.services.humanservice import HumanService

# ---------------------------------------------------------------- body
macro = {"gender": 1.0, "age": 0.55, "muscle": 0.75, "weight": 0.58, "proportions": 0.6, "height": 0.58,
         "cupsize": 0.5, "firmness": 0.5, "race": {"asian": 0.0, "caucasian": 1.0, "african": 0.0}}
base = HumanService.create_human(macro_detail_dict=macro)
rig = HumanService.add_builtin_rig(base, "game_engine")
rig.name = "VikingRig"
for m in list(base.modifiers):
    if m.type == 'MASK': base.modifiers.remove(m)
bpy.context.view_layer.objects.active = base
if base.data.shape_keys:
    bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
# MakeHuman CC0 assets (skin, eyes, brows, lashes, teeth, hair) through the compiled-asset bridge
import importlib.util
_spec = importlib.util.spec_from_file_location("mh_assets", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mh_assets.py"))
mh = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(mh)
SKIN, EYE_COLOUR, HAIR_STYLE = "middleage_caucasian_male", "bluegreen", "short02"
HAIR_TINT = (0.26, 0.15, 0.07)            # chestnut brown; the game re-tints per man
mh.apply_skin(base, SKIN)
BONES = set(b.name for b in rig.data.bones)
vg_index = {g.name: g.index for g in base.vertex_groups}

def in_group(v, name, thr=0.5):
    gi = vg_index.get(name)
    return gi is not None and any(g.group == gi and g.weight >= thr for g in v.groups)

def dominant_bone(v):
    best, bw = None, 0
    for g in v.groups:
        n = base.vertex_groups[g.group].name
        if n in BONES and g.weight > bw: best, bw = n, g.weight
    return best

def centroid(name):
    pts = [v.co for v in base.data.vertices if in_group(v, name, 0.01)]
    return sum(pts, Vector()) / len(pts)

LM = {k: centroid(k) for k in ["joint-mouth", "joint-jaw", "joint-neck", "joint-head", "joint-pelvis", "joint-l-knee", "joint-l-eye", "joint-r-eye", "joint-l-ankle"]}
pelvis_z, knee_z, ankle_z = LM["joint-pelvis"].z, LM["joint-l-knee"].z, LM["joint-l-ankle"].z
eye_z = (LM["joint-l-eye"].z + LM["joint-r-eye"].z) / 2
print("LANDMARKS", {k: tuple(round(c, 3) for c in v) for k, v in LM.items()})

def mat(name, color, metal=0.0, rough=0.85):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Metallic"].default_value = metal; p.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*color, 1); m.metallic = metal; m.roughness = rough
    return m

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)

M = {"skin": mat("Skin", srgb("#c99a7c"), 0, .6), "eye": mat("EyeWhite", srgb("#e8e2d8"), 0, .3), "iris": mat("Iris", srgb("#3a4a5a"), 0, .3),
     "hair": mat("Hair", srgb("#8a5a2b"), 0, .9), "tunic": mat("Tunic", srgb("#8a3a2c")), "trim": mat("Trim", srgb("#5a4a32")),
     "trousers": mat("Trousers", srgb("#5b4a3a")), "wraps": mat("Wraps", srgb("#7a705c")), "leather": mat("Leather", srgb("#3b2a1c"), 0, .7),
     "brass": mat("Brass", srgb("#b8902a"), .9, .35), "iron": mat("Iron", srgb("#7a7f86"), .85, .4), "mail": mat("Mail", srgb("#5c6168"), .8, .5)}

def extract(name, keep, offset=0.0, keep_mats=False):
    """Copy the base mesh (keeping skin weights + armature modifier), keep faces whose verts all pass keep(v)."""
    ob = base.copy(); ob.data = base.data.copy(); ob.name = ob.data.name = name
    bpy.context.collection.objects.link(ob)
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    keepv = [keep(base.data.vertices[i]) for i in range(len(bm.verts))]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not all(keepv[v.index] for v in f.verts)], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    if offset:
        bm.normal_update()
        for v in bm.verts: v.co += v.normal * offset
    bm.to_mesh(ob.data); bm.free()
    if not keep_mats: ob.data.materials.clear()
    return ob

def face_mats(ob, pick):
    names = []
    for p in ob.data.polygons:
        c = sum((ob.data.vertices[i].co for i in p.vertices), Vector()) / len(p.vertices)
        n = pick(c)
        if n not in names: names.append(n); ob.data.materials.append(M[n])
        p.material_index = names.index(n)

def rigid(ob, bone):
    """Bind a separately modelled piece fully to one bone."""
    ob.parent = rig
    g = ob.vertex_groups.new(name=bone); g.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
    md = ob.modifiers.new("Armature", 'ARMATURE'); md.object = rig

def smooth_edges(ob, iters=8, interior=0):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    edge = [v for v in bm.verts if v.is_boundary]
    for _ in range(iters): bmesh.ops.smooth_vert(bm, verts=edge, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    if interior:
        inner = [v for v in bm.verts if not v.is_boundary]
        for _ in range(interior): bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(ob.data); bm.free()

def ring_mesh(name, cx_, cy_, z, rx_, ry_, h, thick, matname):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=40, radius1=1, radius2=1, depth=h)
    for v in bm.verts: v.co = Vector((cx_ + v.co.x * rx_, cy_ + v.co.y * ry_, z + v.co.z))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    sol = ob.modifiers.new("Thick", 'SOLIDIFY'); sol.thickness = thick
    bpy.context.view_layer.objects.active = ob; bpy.ops.object.modifier_apply(modifier=sol.name)
    ob.data.materials.append(M[matname]); return ob

parts = []
hand_head = {s: rig.data.bones["hand_" + s].head_local for s in "lr"}
HIDDEN = {"pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r", "thigh_l", "thigh_r", "calf_l", "calf_r", "foot_l", "foot_r", "ball_l", "ball_r"}
def body_keep(v):
    if not in_group(v, "body"): return False
    b = dominant_bone(v)
    if b in ("lowerarm_l", "lowerarm_r"):
        return (v.co - hand_head[b[-1]]).length < 0.045   # a little wrist skin under the sleeve
    return b not in HIDDEN
body = extract("Body", body_keep, keep_mats=True); parts.append(body)        # MakeHuman skin (SSS) kept from the base

eye_mat = mh.material_from_mhmat(os.path.join(mh.MH_DATA, "eyes", "materials", EYE_COLOUR + ".mhmat"), "Eyes", roughness=0.08, alpha_clip=False, tint=(0.8, 0.8, 0.82))
eyes = mh.fit_asset("eyes", "high-poly", base, rig, material=eye_mat, obj_name="Eyes"); parts.append(eyes)
brows = mh.fit_asset("eyebrows", "eyebrow003", base, rig, obj_name="Eyebrows", tint=tuple(c * 0.85 for c in HAIR_TINT)); parts.append(brows)
lashes = mh.fit_asset("eyelashes", "eyelashes01", base, rig, obj_name="Eyelashes", tint=(0.25, 0.18, 0.12)); parts.append(lashes)
teeth = mh.fit_asset("teeth", "teeth_base", base, rig, obj_name="Teeth"); parts.append(teeth)
hair = mh.fit_asset("hair", HAIR_STYLE, base, rig, obj_name="Hair", tint=HAIR_TINT); parts.append(hair)
for o in (brows, lashes, hair):
    for m in o.data.materials: m.diffuse_color = (*([c * 0.85 for c in HAIR_TINT] if o is not lashes else (0.25, 0.18, 0.12)), 1)
for m in hair.data.materials:
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); bs.inputs["Roughness"].default_value = 0.78

def beard_material(tint):
    """Shell-fur beard: each shell (attribute 'shell' 0..1) keeps only the strands whose noise exceeds a rising threshold,
    so hairs thin out toward the tips; 'fade' (rings from the border) feathers the edge. Roots dark, tips lighter."""
    m = bpy.data.materials.new("Beard"); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]; L = nt.links.new
    for attr, val in (("surface_render_method", 'DITHERED'), ("blend_method", 'HASHED')):
        if hasattr(m, attr):
            try: setattr(m, attr, val)
            except Exception: pass
    def node(t, **kw):
        n = nt.nodes.new(t)
        for k, v in kw.items(): setattr(n, k, v)
        return n
    def math(op, a, b):
        n = node('ShaderNodeMath', operation=op)
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: L(x, n.inputs[i])
        return n.outputs[0]
    sh = node('ShaderNodeAttribute', attribute_name="shell").outputs["Fac"]
    fd = node('ShaderNodeAttribute', attribute_name="fade").outputs["Fac"]
    tc = node('ShaderNodeTexCoord'); mp = node('ShaderNodeMapping'); mp.inputs["Scale"].default_value = (760, 760, 110)
    L(tc.outputs["Object"], mp.inputs["Vector"])
    nz = node('ShaderNodeTexNoise'); nz.inputs["Scale"].default_value = 1.0; nz.inputs["Detail"].default_value = 1.0
    L(mp.outputs["Vector"], nz.inputs["Vector"])
    thr = math('ADD', math('MULTIPLY', sh, 0.22), 0.4)
    strand = math('GREATER_THAN', nz.outputs["Fac"], thr)
    feather = math('POWER', fd, math('ADD', math('MULTIPLY', sh, 2.0), 1.0))
    base = math('MULTIPLY', math('LESS_THAN', sh, 0.01), 0.55)                 # root layer: soft, semi-opaque stubble shadow
    alpha = math('MULTIPLY', math('MAXIMUM', strand, base), feather)
    L(alpha, bs.inputs["Alpha"])
    ramp = node('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*[c * 0.25 for c in tint], 1); ramp.color_ramp.elements[1].color = (*[min(1, c * 1.15) for c in tint], 1)
    vary = node('ShaderNodeTexNoise'); vary.inputs["Scale"].default_value = 140
    L(math('ADD', math('MULTIPLY', sh, 0.75), math('MULTIPLY', vary.outputs["Fac"], 0.35)), ramp.inputs["Fac"])
    L(ramp.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.72
    m.diffuse_color = (*tint, 1); m.roughness = 0.8
    return m

# beard: jaw, chin, cheeks, moustache; lips and nose kept clear. Built as 8 fur shells that droop at the chin.
mz, jz, jy = LM["joint-mouth"].z, LM["joint-jaw"].z, LM["joint-jaw"].y
_lip_slot = next((i for i, s in enumerate(base.material_slots) if s.material and "lips" in s.material.name.lower()), None)
LIPS = {vi for p in base.data.polygons if p.material_index == _lip_slot for vi in p.vertices} if _lip_slot is not None else set()
_lipco = [base.data.vertices[i].co for i in LIPS]
_lipfront = min(p.y for p in _lipco) if _lipco else LM["joint-mouth"].y - 0.03
def beard_keep(v):
    c = v.co
    if not (in_group(v, "body") and dominant_bone(v) == "head") or v.index in LIPS or in_group(v, "ears", .2): return False
    if c.y > jy + 0.04 or abs(c.x) > 0.072 or c.z < jz - 0.055: return False
    if any((c - p).length < 0.0035 for p in _lipco): return False               # small clear margin round the lips
    if c.z > mz and c.y < _lipfront - 0.003: return False                       # nose sticks out past the lips
    if abs(c.x) < 0.03 and c.z > mz + 0.017: return False                       # nostrils / nose base
    if abs(c.x) < 0.045: return c.z < mz + 0.014                                # moustache under the nose, chin, throat
    if c.z < mz + 0.006: return True                                            # jaw
    return c.z < eye_z - 0.078 + (abs(c.x) - 0.045) * 0.9 and c.y > LM["joint-mouth"].y - 0.005   # cheeks / sideburn line
beard = extract("Beard", beard_keep, 0.0012)
smooth_edges(beard, 6, 0)
bm = bmesh.new(); bm.from_mesh(beard.data); bm.verts.ensure_lookup_table(); bm.normal_update()
ring = {v: 0 for v in bm.verts if v.is_boundary}; front = list(ring)
while front:
    nxt = []
    for v in front:
        for e in v.link_edges:
            o = e.other_vert(v)
            if o not in ring: ring[o] = ring[v] + 1; nxt.append(o)
    front = nxt
L_sh, L_fd = bm.verts.layers.float.new("shell"), bm.verts.layers.float.new("fade")
orig = list(bm.verts); onorm = {v: v.normal.copy() for v in orig}; oco = {v: v.co.copy() for v in orig}
for v in orig: v[L_sh] = 0.0; v[L_fd] = min(1.0, (ring.get(v, 6) + 0.3) / 5.0)
NSH = 8
for k in range(1, NSH):
    t = k / (NSH - 1)
    res = bmesh.ops.duplicate(bm, geom=[f for f in bm.faces if f.verts[0][L_sh] == 0.0] + orig)
    for src, dst in res["vert_map"].items():
        if not isinstance(src, bmesh.types.BMVert) or src not in onorm: continue
        below = min(0.045, max(0.0, (mz - 0.006) - oco[src].z))                 # chin & jaw grow longer, hanging down
        dst.co = oco[src] + onorm[src] * t * (0.004 + 0.45 * below) + Vector((0, -0.25 * below * t, -0.75 * below * t * t))
        dst[L_sh] = t; dst[L_fd] = src[L_fd]
bm.to_mesh(beard.data); bm.free()
beard.data.materials.append(beard_material(HAIR_TINT)); parts.append(beard)

# tunic + trousers from the tights helper: torso and sleeves in tunic wool, legs as trousers, shins wrapped
tights = extract("Clothes", lambda v: in_group(v, "helper-tights") and v.co.z > ankle_z + 0.08 and v.co.z < LM["joint-neck"].z + 0.012, 0.004)
face_mats(tights, lambda c: "tunic" if c.z > pelvis_z - 0.02 else ("wraps" if c.z < knee_z - 0.03 else "trousers"))
smooth_edges(tights, 6); parts.append(tights)
bmT = bmesh.new(); bmT.from_mesh(tights.data)
hole = [v.co.copy() for v in bmT.verts if v.is_boundary and v.co.z > LM["joint-neck"].z - 0.09]; bmT.free()
neckv = [v.co for v in base.data.vertices if in_group(v, "body") and dominant_bone(v) == "neck_01"]
if hole and neckv:
    ncx = sum(p.x for p in hole) / len(hole); ncy = sum(p.y for p in hole) / len(hole); nz = sum(p.z for p in hole) / len(hole)
    hrx = max(abs(p.x - ncx) for p in hole) + 0.006; hry = max(abs(p.y - ncy) for p in hole) + 0.006
    nl = [p for p in neckv if abs(p.z - (nz + 0.035)) < 0.012] or neckv
    nrx = max(abs(p.x - ncx) for p in nl) + 0.008; nry = max(abs(p.y - ncy) for p in nl) + 0.008
    bmc = bmesh.new(); bmesh.ops.create_cone(bmc, cap_ends=False, segments=40, radius1=1, radius2=1, depth=1)
    for v in bmc.verts:
        t = v.co.z + 0.5   # 0 bottom (hole) .. 1 top (neck)
        rx_, ry_ = hrx + (nrx - hrx) * t, hry + (nry - hry) * t
        v.co = Vector((ncx + v.co.x * rx_, ncy + v.co.y * ry_, nz - 0.008 + t * 0.022))
    mc = bpy.data.meshes.new("Collar"); bmc.to_mesh(mc); bmc.free()
    collar = bpy.data.objects.new("Collar", mc); bpy.context.collection.objects.link(collar)
    sol = collar.modifiers.new("Thick", 'SOLIDIFY'); sol.thickness = 0.006
    bpy.context.view_layer.objects.active = collar; bpy.ops.object.modifier_apply(modifier=sol.name)
    collar.data.materials.append(M["trim"])
    rigid(collar, "spine_03"); parts.append(collar)

# knee-length tunic skirt from the skirt helper, flared at the hem
skirt = extract("TunicSkirt", lambda v: in_group(v, "helper-skirt") and v.co.z > knee_z + 0.04, 0.008)
zs = [v.co.z for v in skirt.data.vertices]; top, bot = max(zs), min(zs)
cx = sum(v.co.x for v in skirt.data.vertices) / len(zs); cy = sum(v.co.y for v in skirt.data.vertices) / len(zs)
for v in skirt.data.vertices:
    t = (top - v.co.z) / (top - bot); s = 1 + 0.22 * t * t
    v.co.x = cx + (v.co.x - cx) * s; v.co.y = cy + (v.co.y - cy) * s
face_mats(skirt, lambda c: "trim" if c.z < bot + 0.025 else "tunic"); parts.append(skirt)

# boots: the feet and ankles, thickened leather
def boot_keep(v):
    return in_group(v, "body") and (dominant_bone(v) in ("foot_l", "foot_r", "ball_l", "ball_r") or (dominant_bone(v) in ("calf_l", "calf_r") and v.co.z < ankle_z + 0.11))
bmB = bmesh.new()
weights = []   # (bone) per vertex, filled in creation order
for side in "lr":
    fv = [v.co for v in base.data.vertices if in_group(v, "body") and dominant_bone(v) in ("foot_" + side, "ball_" + side)]
    x0, x1 = min(p.x for p in fv), max(p.x for p in fv); y0, y1 = min(p.y for p in fv), max(p.y for p in fv)
    fcx, fcy = (x0 + x1) / 2, (y0 + y1) / 2
    cv = [v.co for v in base.data.vertices if in_group(v, "body") and dominant_bone(v) == "calf_" + side and abs(v.co.z - (ankle_z + 0.08)) < 0.015]
    ccx = sum(p.x for p in cv) / len(cv); ccy = sum(p.y for p in cv) / len(cv); cr = max((Vector((p.x - ccx, p.y - ccy, 0))).length for p in cv) + 0.014
    # shoe: half ellipsoid on a flat sole, toe rounded
    tmp = bmesh.new(); bmesh.ops.create_uvsphere(tmp, u_segments=20, v_segments=12, radius=1)
    for v in tmp.verts:
        z = max(v.co.z, -0.15)
        v.co = Vector((fcx + v.co.x * ((x1 - x0) / 2 + 0.014), fcy + v.co.y * ((y1 - y0) / 2 + 0.016), (z + 0.15) / 1.15 * (ankle_z + 0.035) - 0.002))
    me_t = bpy.data.meshes.new("t"); tmp.to_mesh(me_t); n0 = len(bmB.verts); bmB.from_mesh(me_t); bpy.data.meshes.remove(me_t); tmp.free()
    weights += ["foot_" + side] * (len(bmB.verts) - n0)
    # shaft from the ankle to mid-shin
    tmp = bmesh.new(); bmesh.ops.create_cone(tmp, cap_ends=False, segments=20, radius1=cr * 0.95, radius2=cr, depth=0.13)
    for v in tmp.verts: v.co = Vector((ccx + v.co.x, ccy + v.co.y, ankle_z + 0.05 + v.co.z))
    me_t = bpy.data.meshes.new("t"); tmp.to_mesh(me_t); n0 = len(bmB.verts); bmB.from_mesh(me_t); bpy.data.meshes.remove(me_t); tmp.free()
    weights += [("calf_" + side if True else "") for _ in range(len(bmB.verts) - n0)]
mb = bpy.data.meshes.new("Boots"); bmB.to_mesh(mb); bmB.free()
boots = bpy.data.objects.new("Boots", mb); bpy.context.collection.objects.link(boots); boots.parent = rig
groups = {}
for i, bn in enumerate(weights):
    if bn not in groups: groups[bn] = boots.vertex_groups.new(name=bn)
    groups[bn].add([i], 1.0, 'REPLACE')
md = boots.modifiers.new("Armature", 'ARMATURE'); md.object = rig
boots.data.materials.append(M["leather"]); parts.append(boots)

# belt + buckle around the waist (top of the skirt)
ring = [v.co for v in skirt.data.vertices if v.co.z > top - 0.03]
rx = max(abs(p.x - cx) for p in ring) + 0.006; ry = max(abs(p.y - cy) for p in ring) + 0.006
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=False, segments=40, radius1=1, radius2=1, depth=0.05)
for v in bm.verts: v.co = Vector((cx + v.co.x * rx, cy + v.co.y * ry, top - 0.03 + v.co.z))
tmp = bmesh.new(); bmesh.ops.create_cube(tmp, size=1)
for v in tmp.verts: v.co = Vector((cx + v.co.x * 0.05, cy - ry - 0.006 + v.co.y * 0.01, top - 0.03 + v.co.z * 0.055))
me_t = bpy.data.meshes.new("t"); tmp.to_mesh(me_t); tmp.free(); n_belt = len(bm.faces); bm.from_mesh(me_t); bpy.data.meshes.remove(me_t)
bm.faces.ensure_lookup_table()
for k, f in enumerate(bm.faces): f.material_index = 0 if k < n_belt else 1
bme = bpy.data.meshes.new("Belt"); bm.to_mesh(bme); bm.free()
belt = bpy.data.objects.new("Belt", bme); bpy.context.collection.objects.link(belt)
sol = belt.modifiers.new("Thick", 'SOLIDIFY'); sol.thickness = 0.008
bpy.context.view_layer.objects.active = belt; bpy.ops.object.modifier_apply(modifier=sol.name)
belt.data.materials.append(M["leather"]); belt.data.materials.append(M["brass"])
rigid(belt, "pelvis"); parts.append(belt)

# helmet: spangenhelm dome with brow band, crest strips and nasal guard
sc = [v.co for v in base.data.vertices if in_group(v, "scalp", 0.3)]
hc = sum(sc, Vector()) / len(sc)
brow = eye_z + 0.03
up = [v.co for v in base.data.vertices if in_group(v, "body") and dominant_bone(v) == "head" and v.co.z > brow - 0.01 and not in_group(v, "ears", .2)]
hc = Vector((0.0, (min(p.y for p in up) + max(p.y for p in up)) / 2, 0))
hx = max(abs(p.x) for p in up) + 0.02; hy = (max(p.y for p in up) - min(p.y for p in up)) / 2 + 0.02; hz_top = max(p.z for p in up) + 0.02
face_y = min(v.co.y for v in base.data.vertices if in_group(v, "body") and dominant_bone(v) == "head")
bm = bmesh.new()
def add_piece(geom_fn):
    tmp = bmesh.new(); geom_fn(tmp); me = bpy.data.meshes.new("tmp"); tmp.to_mesh(me); tmp.free(); bm.from_mesh(me); bpy.data.meshes.remove(me)
def dome(b):
    bmesh.ops.create_uvsphere(b, u_segments=32, v_segments=16, radius=1.0)
    bmesh.ops.delete(b, geom=[v for v in b.verts if v.co.z < -0.01], context='VERTS')
    for v in b.verts: v.co = Vector((v.co.x * hx, hc.y + v.co.y * hy, brow + max(v.co.z, 0) * (hz_top - brow)))
def band(b):
    bmesh.ops.create_cone(b, cap_ends=False, segments=32, radius1=1, radius2=1, depth=0.026)
    for v in b.verts: v.co = Vector((v.co.x * (hx + 0.004), hc.y + v.co.y * (hy + 0.004), brow + 0.008 + v.co.z))
def face_y_at(z):
    ys = [v.co.y for v in base.data.vertices if in_group(v, "body") and abs(v.co.x) < 0.012 and abs(v.co.z - z) < 0.006 and dominant_bone(v) == "head"]
    return min(ys) if ys else face_y
def nasal(b):
    zs_ = [brow + 0.008, brow - 0.02, eye_z - 0.035]
    pts = [Vector((0, face_y_at(z) - 0.007, z)) for z in zs_]
    for a_, b_ in zip(pts, pts[1:]):
        new = bmesh.ops.create_cube(b, size=1)['verts']
        mid = (a_ + b_) / 2; L = (b_ - a_).length; ang = math.atan2(b_.y - a_.y, a_.z - b_.z)
        for v in new:
            x, y, z = v.co.x * 0.016, v.co.y * 0.005, v.co.z * L
            yz = Vector((y * math.cos(ang) - z * math.sin(ang), y * math.sin(ang) + z * math.cos(ang)))
            v.co = Vector((x, mid.y + yz.x, mid.z + yz.y)); v.tag = True
def crest(b):
    bmesh.ops.create_cube(b, size=1)
    for v in b.verts:
        t = v.co.y + 0.5; ang = math.pi * t
        v.co = Vector((hc.x + v.co.x * 0.016, hc.y - math.cos(ang) * (hy + 0.003), brow + math.sin(ang) * (hz_top - brow + 0.003) + v.co.z * 0.006))
for fn in (dome, band, nasal): add_piece(fn)
hm = bpy.data.meshes.new("Helmet"); bm.to_mesh(hm); bm.free()
helmet = bpy.data.objects.new("Helmet", hm); bpy.context.collection.objects.link(helmet)
sol = helmet.modifiers.new("Thick", 'SOLIDIFY'); sol.thickness = 0.004
bpy.context.view_layer.objects.active = helmet; bpy.ops.object.modifier_apply(modifier=sol.name)
helmet.data.materials.append(M["iron"])
rigid(helmet, "head"); parts.append(helmet)

# mail byrnie (optional layer for armoured troops): over the tunic, short sleeves, to mid-thigh
mail = extract("Mail", lambda v: in_group(v, "helper-tights") and v.co.z > pelvis_z - 0.02 and dominant_bone(v) not in ("lowerarm_l", "lowerarm_r", "hand_l", "hand_r") and not (dominant_bone(v) in ("upperarm_l", "upperarm_r") and abs(v.co.x) > 0.27), 0.013)
mail.data.materials.append(M["mail"]); parts.append(mail)

for p in parts:
    p.parent = rig
    if not any(m.type == 'ARMATURE' for m in p.modifiers):
        md = p.modifiers.new("Armature", 'ARMATURE'); md.object = rig
base.hide_render = True; base.hide_set(True)
for p in parts:
    for poly in p.data.polygons: poly.use_smooth = True

# ---------------------------------------------------------------- report weights (clothing must follow the skeleton)
for p in parts:
    bone_groups = [g for g in p.vertex_groups if g.name in BONES]
    weighted = sum(1 for v in p.data.vertices if any(p.vertex_groups[g.group].name in BONES and g.weight > 0 for g in v.groups))
    print("PART", p.name, "verts", len(p.data.vertices), "weighted", weighted, "mats", [m.name for m in p.data.materials])

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "viking_build.blend"))
print("SAVED_BLEND")
