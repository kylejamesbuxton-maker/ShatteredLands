"""
Unreal editor Python (PythonScript commandlet): gives every cloth / leather / mail / metal / wood / fur piece a real
surface instead of a flat colour, and lays the mirrored ground tiles.

- Imports the seamless detail textures made by blender/make_detail_textures.py (unreal_export/Materials).
- Builds M_SL_Surface: BOX (triplanar) projection in the mesh's own pre-skinning space, so the pattern never stretches
  on walls/limbs and doesn't swim when the Viking animates. Detail texture x Tint -> Base Color, blended detail normal,
  Roughness / Metallic parameters, Scale = texture repeats per cm.
- One material instance per Blender material name (colour/roughness/metal from material_colors.json), assigned by
  slot name on all 13 characters. Skin, hair, eyes, brows, lashes and beard (MI_* from materials.py) are left alone.
- Imports SM_TerrainPatch_20m_MX/MY/MXY (real mirrored geometry) and gives them M_SL_Terrain.
"""
import os, json
import unreal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "unreal_export"))
DEST = "/Game/ShatteredLands"; MATS = DEST + "/Materials"; DET = MATS + "/Detail"
tools = unreal.AssetToolsHelpers.get_asset_tools(); eal = unreal.EditorAssetLibrary; mel = unreal.MaterialEditingLibrary


def log(*a): unreal.log_warning("SL_ " + " ".join(str(x) for x in a))


def sp(o, k, v):
    try: o.set_editor_property(k, v)
    except Exception as e: log("skip", k, e)


def imp(src, dest, replace=True):
    t = unreal.AssetImportTask(); t.filename = src; t.destination_path = dest; t.automated = True; t.save = True; t.replace_existing = replace
    tools.import_asset_tasks([t]); return list(t.imported_object_paths or [])

# ---------------------------------------------------------------- detail textures
KINDS = ["Wool", "Linen", "Quilt", "Leather", "Mail", "Steel", "Wood", "Fur", "Gilt"]
TEXD, TEXN = {}, {}
for k in KINDS:
    for suf, store in (("D", TEXD), ("N", TEXN)):
        imp(os.path.join(ROOT, "Materials", "T_SL_%s_%s.png" % (k, suf)), DET)
        t = eal.load_asset("%s/T_SL_%s_%s" % (DET, k, suf))
        sp(t, "max_texture_size", 1024)
        if suf == "N": sp(t, "srgb", False); sp(t, "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        eal.save_loaded_asset(t); store[k] = t
log("detail textures", len(TEXD) + len(TEXN))

# ---------------------------------------------------------------- M_SL_Surface (box / triplanar in pre-skinned local space)
path = MATS + "/M_SL_Surface"
if eal.does_asset_exist(path): eal.delete_asset(path)
m = tools.create_asset("M_SL_Surface", MATS, unreal.Material, unreal.MaterialFactoryNew())
X = [-2400]


def E(cls, x, y, **props):
    n = mel.create_material_expression(m, cls, x, y)
    for k, v in props.items(): sp(n, k, v)
    return n


def link(a, ao, b, bi): mel.connect_material_expressions(a, ao, b, bi)


def mask(src, r, g, b, x, y):
    n = E(unreal.MaterialExpressionComponentMask, x, y, r=r, g=g, b=b, a=False); link(src, "", n, ""); return n


# pre-skinned position/normal exist only in the vertex shader: pass them to the pixel shader through interpolators
pos0 = E(unreal.MaterialExpressionPreSkinnedPosition, -2700, 0); pos = E(unreal.MaterialExpressionVertexInterpolator, -2500, 0); link(pos0, "", pos, "")
nrm0 = E(unreal.MaterialExpressionPreSkinnedNormal, -2700, 400); nrm = E(unreal.MaterialExpressionVertexInterpolator, -2500, 400); link(nrm0, "", nrm, "")
scale = E(unreal.MaterialExpressionScalarParameter, -2400, 200, parameter_name="Scale", default_value=1.0 / 15.0)
sc = E(unreal.MaterialExpressionMultiply, -2200, 100); link(pos, "", sc, "A"); link(scale, "", sc, "B")
uvx, uvy, uvz = mask(sc, False, True, True, -2000, -100), mask(sc, True, False, True, -2000, 100), mask(sc, True, True, False, -2000, 300)
# weights = |n|^4 / sum
ab = E(unreal.MaterialExpressionAbs, -2200, 450); link(nrm, "", ab, "")
pw = E(unreal.MaterialExpressionPower, -2050, 450); link(ab, "", pw, "Base"); sp(pw, "const_exponent", 4.0)
one = E(unreal.MaterialExpressionConstant3Vector, -2050, 600, constant=unreal.LinearColor(1, 1, 1, 1))
dt = E(unreal.MaterialExpressionDotProduct, -1900, 550); link(pw, "", dt, "A"); link(one, "", dt, "B")
wv = E(unreal.MaterialExpressionDivide, -1750, 450); link(pw, "", wv, "A"); link(dt, "", wv, "B")
wx, wy, wz = mask(wv, True, False, False, -1600, 400), mask(wv, False, True, False, -1600, 500), mask(wv, False, False, True, -1600, 600)


def triplanar(param, tex, y0, normal=False):
    obj = E(unreal.MaterialExpressionTextureObjectParameter, -1800, y0, parameter_name=param, texture=tex)
    if normal: sp(obj, "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    acc = None
    for i, (uv, w) in enumerate(((uvx, wx), (uvy, wy), (uvz, wz))):
        s = E(unreal.MaterialExpressionTextureSample, -1500, y0 + i * 150, texture=tex)
        if normal: sp(s, "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        link(obj, "", s, "Tex"); link(uv, "", s, "UVs")
        mul = E(unreal.MaterialExpressionMultiply, -1250, y0 + i * 150); link(s, "RGB", mul, "A"); link(w, "", mul, "B")
        if acc is None: acc = mul
        else:
            add = E(unreal.MaterialExpressionAdd, -1050, y0 + i * 150); link(acc, "", add, "A"); link(mul, "", add, "B"); acc = add
    return acc

detail = triplanar("Detail", TEXD["Wool"], -900)
dnorm = triplanar("DetailNormal", TEXN["Wool"], 200, normal=True)
tint = E(unreal.MaterialExpressionVectorParameter, -1000, -1100, parameter_name="Tint", default_value=unreal.LinearColor(0.5, 0.5, 0.5, 1))
bc = E(unreal.MaterialExpressionMultiply, -700, -900); link(detail, "", bc, "A"); link(tint, "", bc, "B")
mel.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
flat = E(unreal.MaterialExpressionConstant3Vector, -900, 600, constant=unreal.LinearColor(0, 0, 1, 1))
nstr = E(unreal.MaterialExpressionScalarParameter, -900, 750, parameter_name="NormalStrength", default_value=0.8)
nl = E(unreal.MaterialExpressionLinearInterpolate, -700, 400); link(flat, "", nl, "A"); link(dnorm, "", nl, "B"); link(nstr, "", nl, "Alpha")
nn = E(unreal.MaterialExpressionNormalize, -500, 400); link(nl, "", nn, "")
mel.connect_material_property(nn, "", unreal.MaterialProperty.MP_NORMAL)
# roughness varies a little with the detail (worn high spots smoother)
rgh = E(unreal.MaterialExpressionScalarParameter, -900, -300, parameter_name="Roughness", default_value=0.8)
dm = mask(detail, True, False, False, -900, -200)
rv = E(unreal.MaterialExpressionLinearInterpolate, -650, -250); link(rgh, "", rv, "A")
rlo = E(unreal.MaterialExpressionMultiply, -800, -150); link(rgh, "", rlo, "A"); sp(rlo, "const_b", 0.8); link(rlo, "", rv, "B"); link(dm, "", rv, "Alpha")
mel.connect_material_property(rv, "", unreal.MaterialProperty.MP_ROUGHNESS)
met = E(unreal.MaterialExpressionScalarParameter, -650, -50, parameter_name="Metallic", default_value=0.0)
mel.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
mel.recompile_material(m); eal.save_loaded_asset(m); log("M_SL_Surface built")

# ---------------------------------------------------------------- instances per Blender material
COLORS = json.load(open(os.path.join(ROOT, "Materials", "material_colors.json")))
TILE_CM = {"Wool": 14, "Linen": 9, "Quilt": 30, "Leather": 22, "Mail": 26, "Steel": 45, "Wood": 55, "Fur": 18, "Gilt": 20}
RULES = [("Mail", ("mail", "byrnie", "chausse", "coif", "aventail", "curtain")), ("Quilt", ("padd", "quilt", "gambeson", "coat")),
         ("Fur", ("fur",)), ("Gilt", ("brass", "gilt", "gold", "silver", "bronze")),
         ("Steel", ("iron", "steel", "boss", "helm", "forged", "rim", "nasal", "blade", "spear", "sword", "metal")),
         ("Leather", ("leather", "belt", "boot", "grip", "rawhide", "shoe", "strap", "sheath", "scabbard", "bracer")),
         ("Wood", ("wood", "yew", "ash", "shaft", "plank", "shield", "paint", "horn", "haft", "board")),
         ("Linen", ("linen", "white", "surcoat", "shirt", "doublet", "string", "rose_w"))]
SKIP_PREFIX = ("MI_Skin", "MI_Eyes", "MI_Lashes", "MI_Brow", "MI_Hair", "MI_Beard", "M_SL_", "MI_Surf")


def kind_of(slot):
    s = slot.lower()
    for k, keys in RULES:
        if any(x in s for x in keys): return k
    return "Wool"


made = {}


def surface_mi(slot):
    if slot in made: return made[slot]
    k = kind_of(slot); c = COLORS.get(slot, {"color": [0.5, 0.5, 0.5], "rough": 0.8, "metal": 0.0})
    col = c["color"]
    if slot.lower() == "shieldpaint": col = [0.45, 0.06, 0.04]            # game re-paints this per warband; madder red default
    metal = 1.0 if k in ("Steel", "Gilt", "Mail") else min(c["metal"], 1.0)
    rough = {"Steel": 0.32, "Gilt": 0.3, "Mail": 0.45}.get(k, max(0.55, c["rough"]))
    name = "MI_Surf_" + slot; p = MATS + "/Instances/" + name
    if eal.does_asset_exist(p): eal.delete_asset(p)
    inst = tools.create_asset(name, MATS + "/Instances", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(inst, m)
    mel.set_material_instance_texture_parameter_value(inst, "Detail", TEXD[k]); mel.set_material_instance_texture_parameter_value(inst, "DetailNormal", TEXN[k])
    mel.set_material_instance_vector_parameter_value(inst, "Tint", unreal.LinearColor(col[0], col[1], col[2], 1.0))
    mel.set_material_instance_scalar_parameter_value(inst, "Scale", 1.0 / TILE_CM[k])
    mel.set_material_instance_scalar_parameter_value(inst, "Roughness", rough)
    mel.set_material_instance_scalar_parameter_value(inst, "Metallic", metal)
    mel.set_material_instance_scalar_parameter_value(inst, "NormalStrength", {"Steel": 0.3, "Gilt": 0.4}.get(k, 0.8))
    eal.save_loaded_asset(inst); made[slot] = inst; return inst


meshes = ["Characters/Viking/SK_Viking_Warrior"] + ["Characters/English/SM_English_Tier%d" % i for i in range(1, 7)] + ["Characters/VikingTiers/SM_Viking_Tier%d" % i for i in range(1, 7)]
for rel in meshes:
    a = eal.load_asset(DEST + "/" + rel); n = 0
    if isinstance(a, unreal.SkeletalMesh):
        mats = list(a.get_editor_property("materials"))
        for s in mats:
            cur = s.get_editor_property("material_interface")
            if (cur and cur.get_name().startswith(SKIP_PREFIX[:-1])) or str(s.get_editor_property("material_slot_name")).startswith("SC_"): continue
            s.set_editor_property("material_interface", surface_mi(str(s.get_editor_property("material_slot_name")))); n += 1
        a.set_editor_property("materials", mats)
    else:
        for i, s in enumerate(a.get_editor_property("static_materials")):
            cur = s.get_editor_property("material_interface")
            if (cur and cur.get_name().startswith(SKIP_PREFIX[:-1])) or str(s.get_editor_property("material_slot_name")).startswith("SC_"): continue
            a.set_material(i, surface_mi(str(s.get_editor_property("material_slot_name")))); n += 1
    eal.save_loaded_asset(a); log(rel.split("/")[-1], "surfaces:", n)
log("surface instances", len(made), sorted(set(kind_of(s) for s in made)))

# ---------------------------------------------------------------- mirrored ground tiles
ter_mat = eal.load_asset(MATS + "/M_SL_Terrain")
for tag in ("MX", "MY", "MXY"):
    t = unreal.AssetImportTask(); t.filename = os.path.join(ROOT, "Terrain", "SM_TerrainPatch_20m_%s.fbx" % tag)
    t.destination_path = DEST + "/Terrain"; t.automated = True; t.save = True; t.replace_existing = True
    ui = unreal.FbxImportUI(); sp(ui, "import_materials", False); sp(ui, "import_textures", False); sp(ui, "import_as_skeletal", False)
    sp(ui.get_editor_property("static_mesh_import_data"), "combine_meshes", True); t.options = ui
    tools.import_asset_tasks([t])
    sm = eal.load_asset(DEST + "/Terrain/SM_TerrainPatch_20m_" + tag)
    if sm and ter_mat: sm.set_material(0, ter_mat); eal.save_loaded_asset(sm)
log("mirrored ground tiles imported")
