"""
Unreal editor Python (PythonScript commandlet is fine): builds proper Unreal materials for the imported characters
and battlefield ground, and assigns them by material-slot name.

FBX carries only flat colours from Blender's node materials, so skin, hair, brows, lashes and eyes came in white.
This imports the original MakeHuman CC0 textures and wires them into a few master materials:
  M_SL_Skin (texture base colour), M_SL_Masked (alpha-tested, two-sided cards: hair/brows/lashes),
  M_SL_Opaque (eyes), M_SL_Beard (tinted, noise-cut fur), M_SL_Terrain (baked albedo/normal/roughness).
Each character gets its own hair/brow/beard tint, matching the Blender tier scripts (VK_CAST / MH_CAST).
Lines starting with SL_ are progress markers.
"""
import os
import unreal

MH = os.path.join(os.environ.get("LOCALAPPDATA", ""), "makehuman-community", "makehuman", "data")
KIT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "unreal_export"))
DEST = "/Game/ShatteredLands"; MATS = DEST + "/Materials"; TEX = DEST + "/Characters/Textures"
tools = unreal.AssetToolsHelpers.get_asset_tools(); eal = unreal.EditorAssetLibrary; mel = unreal.MaterialEditingLibrary


def log(*a): unreal.log_warning("SL_ " + " ".join(str(x) for x in a))


def sp(o, k, v):
    try: o.set_editor_property(k, v)
    except Exception as e: log("skip", k, e)


# ---------------------------------------------------------------- textures
def imp(src, dest, max_size=0, srgb=True, normal=False):
    name = os.path.splitext(os.path.basename(src))[0]
    path = dest + "/" + name
    if not eal.does_asset_exist(path):
        t = unreal.AssetImportTask(); t.filename = src; t.destination_path = dest; t.automated = True; t.save = True; t.replace_existing = True
        tools.import_asset_tasks([t])
    tex = eal.load_asset(path)
    if tex:
        if max_size: sp(tex, "max_texture_size", max_size)
        sp(tex, "srgb", srgb)
        if normal: sp(tex, "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        eal.save_loaded_asset(tex)
    return tex

skins = {k: imp(os.path.join(MH, "skins", "textures", "%s_lightskinned_male_diffuse.png" % k), TEX, 2048) for k in ("young", "middleage")}
hair = {h: imp(os.path.join(MH, "hair", h, h + "_diffuse.png"), TEX, 1024) for h in ("short02", "long01")}
hair_n = imp(os.path.join(MH, "hair", "short02", "short02_normal.png"), TEX, 1024, srgb=False, normal=True)
brow = imp(os.path.join(MH, "eyebrows", "eyebrow003", "eyebrow003.png"), TEX, 512)
lash = imp(os.path.join(MH, "eyelashes", "eyelashes01", "eyelashes01.png"), TEX, 256)
eyes = {}
for c in ("lightblue", "blue", "bluegreen", "grey", "brownlight", "brown", "ice"):
    p = os.path.join(MH, "eyes", "materials", c + "_eye.png")
    if os.path.exists(p): eyes[c] = imp(p, TEX, 512)
log("textures", len(skins) + len(hair) + 3 + len(eyes))


# ---------------------------------------------------------------- master materials
def new_material(name):
    path = MATS + "/" + name
    if eal.does_asset_exist(path): eal.delete_asset(path)
    return tools.create_asset(name, MATS, unreal.Material, unreal.MaterialFactoryNew())


def expr(m, cls, x, y, **props):
    n = mel.create_material_expression(m, cls, x, y)
    for k, v in props.items(): sp(n, k, v)
    return n


def tex_param(m, name, tex, x, y, normal=False):
    n = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, x, y, parameter_name=name, texture=tex)
    if normal: sp(n, "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    return n


def scalar(m, name, val, x, y): return expr(m, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=val)
def vector(m, name, col, x, y): return expr(m, unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name, default_value=unreal.LinearColor(*col))


def tinted_base(m, tex, rough):
    t = tex_param(m, "BaseTex", tex, -700, 0); c = vector(m, "Tint", (1, 1, 1, 1), -700, 250)
    mul = expr(m, unreal.MaterialExpressionMultiply, -350, 80)
    mel.connect_material_expressions(t, "RGB", mul, "A"); mel.connect_material_expressions(c, "", mul, "B")
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(scalar(m, "Roughness", rough, -350, 300), "", unreal.MaterialProperty.MP_ROUGHNESS)
    return t

# skin: MakeHuman diffuse; a little softer specular than default
m_skin = new_material("M_SL_Skin"); tinted_base(m_skin, skins["young"], 0.52)
mel.connect_material_property(scalar(m_skin, "Specular", 0.35, -350, 420), "", unreal.MaterialProperty.MP_SPECULAR)
# masked cards (hair, brows, lashes): alpha-tested, two-sided
m_mask = new_material("M_SL_Masked"); t = tinted_base(m_mask, hair["short02"], 0.75)
mel.connect_material_property(t, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
sp(m_mask, "blend_mode", unreal.BlendMode.BLEND_MASKED); sp(m_mask, "two_sided", True); sp(m_mask, "opacity_mask_clip_value", 0.4)
# opaque textured (eyes)
m_opq = new_material("M_SL_Opaque"); tinted_base(m_opq, eyes.get("brown") or list(eyes.values())[0], 0.15)
# beard: tinted, fine world-space noise cuts it into strands; two-sided masked
m_beard = new_material("M_SL_Beard")
bc = vector(m_beard, "Tint", (0.2, 0.12, 0.06, 1), -500, 0); mel.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
nz = expr(m_beard, unreal.MaterialExpressionNoise, -500, 250, scale=2.5, levels=3, output_min=0.0, output_max=1.0)
mel.connect_material_property(nz, "", unreal.MaterialProperty.MP_OPACITY_MASK)
mel.connect_material_property(scalar(m_beard, "Roughness", 0.8, -500, 450), "", unreal.MaterialProperty.MP_ROUGHNESS)
sp(m_beard, "blend_mode", unreal.BlendMode.BLEND_MASKED); sp(m_beard, "two_sided", True); sp(m_beard, "opacity_mask_clip_value", 0.45)
# battlefield ground: baked albedo / normal / roughness from Blender
tA = eal.load_asset(DEST + "/Terrain/Textures/T_Terrain_Albedo"); tN = eal.load_asset(DEST + "/Terrain/Textures/T_Terrain_Normal"); tR = eal.load_asset(DEST + "/Terrain/Textures/T_Terrain_Roughness")
m_ter = new_material("M_SL_Terrain")
# the baked albedo was authored for the browser renderer (shown at x0.62 there); Unreal's physically-based light
# needs the same darkening, and bare earth should never go glossy, so roughness is kept in 0.75..1
a = tex_param(m_ter, "Albedo", tA, -800, -200)
# the pale grey dried-mud patches read as snow under a physical sun: pull light areas toward dark warm mud
lum = expr(m_ter, unreal.MaterialExpressionDotProduct, -650, -400); mel.connect_material_expressions(a, "RGB", lum, "A")
mel.connect_material_expressions(expr(m_ter, unreal.MaterialExpressionConstant3Vector, -800, -450, constant=unreal.LinearColor(0.3, 0.59, 0.11, 1)), "", lum, "B")
lsub = expr(m_ter, unreal.MaterialExpressionSubtract, -550, -400, const_b=0.1); mel.connect_material_expressions(lum, "", lsub, "A")
lmul = expr(m_ter, unreal.MaterialExpressionMultiply, -480, -400, const_b=10.0); mel.connect_material_expressions(lsub, "", lmul, "A")
lbright = expr(m_ter, unreal.MaterialExpressionSaturate, -420, -400); mel.connect_material_expressions(lmul, "", lbright, "")
# greyness: blue nearly as strong as red (grass is yellow, earth is brown: both have far less blue than red)
cb = expr(m_ter, unreal.MaterialExpressionComponentMask, -650, -550, r=False, g=False, b=True, a=False); mel.connect_material_expressions(a, "RGB", cb, "")
cr = expr(m_ter, unreal.MaterialExpressionComponentMask, -650, -620, r=True, g=False, b=False, a=False); mel.connect_material_expressions(a, "RGB", cr, "")
cr6 = expr(m_ter, unreal.MaterialExpressionMultiply, -560, -620, const_b=0.6); mel.connect_material_expressions(cr, "", cr6, "A")
gdif = expr(m_ter, unreal.MaterialExpressionSubtract, -480, -580); mel.connect_material_expressions(cb, "", gdif, "A"); mel.connect_material_expressions(cr6, "", gdif, "B")
gmul = expr(m_ter, unreal.MaterialExpressionMultiply, -420, -580, const_b=12.0); mel.connect_material_expressions(gdif, "", gmul, "A")
grey = expr(m_ter, unreal.MaterialExpressionSaturate, -360, -580); mel.connect_material_expressions(gmul, "", grey, "")
lsat = expr(m_ter, unreal.MaterialExpressionMultiply, -300, -480); mel.connect_material_expressions(grey, "", lsat, "A"); mel.connect_material_expressions(lbright, "", lsat, "B")
mud = expr(m_ter, unreal.MaterialExpressionMultiply, -550, -300); mel.connect_material_expressions(a, "RGB", mud, "A")
mel.connect_material_expressions(expr(m_ter, unreal.MaterialExpressionConstant3Vector, -700, -300, constant=unreal.LinearColor(0.42, 0.34, 0.25, 1)), "", mud, "B")
fix = expr(m_ter, unreal.MaterialExpressionLinearInterpolate, -350, -350); mel.connect_material_expressions(a, "RGB", fix, "A")
mel.connect_material_expressions(mud, "", fix, "B"); mel.connect_material_expressions(lsat, "", fix, "Alpha")
ab = expr(m_ter, unreal.MaterialExpressionMultiply, -250, -200); mel.connect_material_expressions(fix, "", ab, "A")
mel.connect_material_expressions(scalar(m_ter, "AlbedoScale", 0.55, -800, -50), "", ab, "B")
mel.connect_material_property(ab, "", unreal.MaterialProperty.MP_BASE_COLOR)
n = tex_param(m_ter, "Normal", tN, -800, 100, normal=True)
nf = expr(m_ter, unreal.MaterialExpressionConstant3Vector, -800, 250, constant=unreal.LinearColor(0, 0, 1, 1))
nl = expr(m_ter, unreal.MaterialExpressionLinearInterpolate, -450, 150); mel.connect_material_expressions(nf, "", nl, "A")
mel.connect_material_expressions(n, "RGB", nl, "B"); mel.connect_material_expressions(scalar(m_ter, "NormalStrength", 0.7, -800, 330), "", nl, "Alpha")
mel.connect_material_property(nl, "", unreal.MaterialProperty.MP_NORMAL)
r = tex_param(m_ter, "Rough", tR, -800, 450)
rl = expr(m_ter, unreal.MaterialExpressionLinearInterpolate, -450, 450, const_a=0.75, const_b=1.0); mel.connect_material_expressions(r, "R", rl, "Alpha")
mel.connect_material_property(rl, "", unreal.MaterialProperty.MP_ROUGHNESS)
mel.connect_material_property(scalar(m_ter, "Specular", 0.3, -450, 600), "", unreal.MaterialProperty.MP_SPECULAR)
for m in (m_skin, m_mask, m_opq, m_beard, m_ter): mel.recompile_material(m); eal.save_loaded_asset(m)
log("master materials built")


# ---------------------------------------------------------------- instances
def mi(name, parent, tex=None, tint=None, rough=None):
    path = MATS + "/Instances/" + name
    if eal.does_asset_exist(path): eal.delete_asset(path)
    inst = tools.create_asset(name, MATS + "/Instances", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(inst, parent)
    if tex: mel.set_material_instance_texture_parameter_value(inst, "BaseTex", tex)
    if tint: mel.set_material_instance_vector_parameter_value(inst, "Tint", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
    if rough is not None: mel.set_material_instance_scalar_parameter_value(inst, "Roughness", rough)
    eal.save_loaded_asset(inst); return inst

# per character: (skin age, eye colour, hair style, hair tint) â€” mirrors the Blender cast tables
CAST = {
    "Characters/Viking/SK_Viking_Warrior": ("middleage", "bluegreen", "short02", (0.26, 0.15, 0.07)),
    "Characters/English/SM_English_Tier1": ("young", "brownlight", "short02", (0.2, 0.12, 0.06)),
    "Characters/English/SM_English_Tier2": ("middleage", "brown", "short01", (0.12, 0.08, 0.05)),
    "Characters/English/SM_English_Tier3": ("young", "bluegreen", "short04", (0.32, 0.2, 0.09)),
    "Characters/English/SM_English_Tier4": ("middleage", "grey", None, (0.15, 0.1, 0.06)),
    "Characters/English/SM_English_Tier5": ("young", "blue", None, (0.25, 0.16, 0.08)),
    "Characters/English/SM_English_Tier6": ("middleage", "brown", "short02", (0.16, 0.1, 0.05)),
    "Characters/VikingTiers/SM_Viking_Tier1": ("young", "lightblue", "long01", (0.42, 0.3, 0.16)),
    "Characters/VikingTiers/SM_Viking_Tier2": ("young", "blue", "short02", (0.55, 0.42, 0.22)),
    "Characters/VikingTiers/SM_Viking_Tier3": ("middleage", "bluegreen", "short02", (0.42, 0.17, 0.06)),
    "Characters/VikingTiers/SM_Viking_Tier4": ("middleage", "grey", None, (0.2, 0.13, 0.07)),
    "Characters/VikingTiers/SM_Viking_Tier5": ("young", "brownlight", None, (0.3, 0.2, 0.1)),
    "Characters/VikingTiers/SM_Viking_Tier6": ("middleage", "ice", None, (0.58, 0.5, 0.38)),
}
skin_mi = {k: mi("MI_Skin_" + k, m_skin, skins[k]) for k in skins}
eye_mi = {k: mi("MI_Eyes_" + k, m_opq, v, (0.85, 0.85, 0.88)) for k, v in eyes.items()}
lash_mi = mi("MI_Lashes", m_mask, lash, (0.18, 0.13, 0.09), 0.6)


def material_for(slot, path, cfg):
    skin, eye, hairstyle, tint = cfg; s = slot.lower(); tag = path.split("/")[-1]
    if s.startswith("human_"): return skin_mi[skin]
    if s.startswith("eyes"): return eye_mi.get(s[5:] or eye) or eye_mi.get(eye)
    if s.startswith("eyelashes"): return lash_mi
    if s.startswith("eyebrow"): return mi("MI_Brow_" + tag, m_mask, brow, tuple(c * 0.8 for c in tint), 0.7)
    if s in ("short02", "long01", "short01", "short03", "short04"):
        return mi("MI_Hair_" + tag, m_mask, hair.get(s, hair["short02"]), tuple(min(1.0, c * 1.6) for c in tint), 0.7)
    if s == "beard": return mi("MI_Beard_" + tag, m_beard, None, tint)
    return None


for rel, cfg in CAST.items():
    asset = eal.load_asset(DEST + "/" + rel)
    if not asset: log("missing", rel); continue
    changed = 0
    if isinstance(asset, unreal.SkeletalMesh):
        mats = list(asset.get_editor_property("materials"))
        for sm in mats:
            new = material_for(str(sm.get_editor_property("material_slot_name")), rel, cfg)
            if new: sm.set_editor_property("material_interface", new); changed += 1
        asset.set_editor_property("materials", mats)
    else:
        for i, sm in enumerate(asset.get_editor_property("static_materials")):
            new = material_for(str(sm.get_editor_property("material_slot_name")), rel, cfg)
            if new: asset.set_material(i, new); changed += 1
    eal.save_loaded_asset(asset); log(rel.split("/")[-1], "slots re-materialed:", changed)

for tag in ("", "_MX", "_MY", "_MXY"):                                   # base tile + its mirrored copies
    ground = eal.load_asset(DEST + "/Terrain/SM_TerrainPatch_20m" + tag)
    if ground: ground.set_material(0, m_ter); eal.save_loaded_asset(ground)
log("ground material set")
log("materials done")
