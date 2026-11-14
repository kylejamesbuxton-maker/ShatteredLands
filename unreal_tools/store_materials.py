"""
Unreal editor Python (PythonScript commandlet): rebuilds the store / scanned asset materials (slots named SC_*) on the
tier meshes from their original texture sets, recorded by blender/export_unreal.py in store_materials.json.

M_SL_PBR: Albedo -> Base Color, Normal (tangent) -> Normal, Mask: R = metallic, A = smoothness
(Unity "MetallicSmoothness" and HDRP "MaskMap" share that layout) -> Roughness = lerp(RoughHi, RoughLo, smoothness).
Textures are imported once into /Game/ShatteredLands/Store/Textures, capped at 2048 px.
"""
import os, json
import unreal

KIT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "unreal_export"))
DEST = "/Game/ShatteredLands"; STORE = DEST + "/Store"; TEX = STORE + "/Textures"
tools = unreal.AssetToolsHelpers.get_asset_tools(); eal = unreal.EditorAssetLibrary; mel = unreal.MaterialEditingLibrary


def log(*a): unreal.log_warning("SL_ " + " ".join(str(x) for x in a))


def sp(o, k, v):
    try: o.set_editor_property(k, v)
    except Exception as e: log("skip", k, e)


def tex(path, srgb=True, normal=False):
    if not path or not os.path.exists(path): return None
    name = "T_" + "".join(c if c.isalnum() else "_" for c in os.path.splitext(os.path.basename(path))[0])
    p = TEX + "/" + name
    if not eal.does_asset_exist(p):
        t = unreal.AssetImportTask(); t.filename = path; t.destination_path = TEX; t.destination_name = name
        t.automated = True; t.save = True; t.replace_existing = True; tools.import_asset_tasks([t])
    a = eal.load_asset(p)
    if a:
        sp(a, "max_texture_size", 2048); sp(a, "srgb", srgb)
        if normal: sp(a, "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        elif not srgb: sp(a, "compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        eal.save_loaded_asset(a)
    return a


# ---------------------------------------------------------------- master
path = STORE + "/M_SL_PBR"
if eal.does_asset_exist(path): eal.delete_asset(path)
m = tools.create_asset("M_SL_PBR", STORE, unreal.Material, unreal.MaterialFactoryNew())
def E(cls, x, y, **kw):
    n = mel.create_material_expression(m, cls, x, y)
    for k, v in kw.items(): sp(n, k, v)
    return n
al = E(unreal.MaterialExpressionTextureSampleParameter2D, -800, -200, parameter_name="Albedo")
nm = E(unreal.MaterialExpressionTextureSampleParameter2D, -800, 100, parameter_name="Normal", sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
mk = E(unreal.MaterialExpressionTextureSampleParameter2D, -800, 400, parameter_name="Mask", sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
mel.connect_material_property(al, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(nm, "RGB", unreal.MaterialProperty.MP_NORMAL)
mul = E(unreal.MaterialExpressionMultiply, -450, 350); mel.connect_material_expressions(mk, "R", mul, "A")
mel.connect_material_expressions(E(unreal.MaterialExpressionScalarParameter, -650, 300, parameter_name="MetalScale", default_value=1.0), "", mul, "B")
mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_METALLIC)
lo = E(unreal.MaterialExpressionScalarParameter, -650, 550, parameter_name="RoughLo", default_value=0.3)
hi = E(unreal.MaterialExpressionScalarParameter, -650, 650, parameter_name="RoughHi", default_value=0.85)
lr = E(unreal.MaterialExpressionLinearInterpolate, -400, 550); mel.connect_material_expressions(hi, "", lr, "A"); mel.connect_material_expressions(lo, "", lr, "B")
mel.connect_material_expressions(mk, "A", lr, "Alpha"); mel.connect_material_property(lr, "", unreal.MaterialProperty.MP_ROUGHNESS)
# ---------------------------------------------------------------- instances
SRC = json.load(open(os.path.join(KIT, "Characters", "VikingTiers", "store_materials.json")))
made = {}
for name, d in SRC.items():
    p = STORE + "/Instances/MI_" + name
    if eal.does_asset_exist(p): eal.delete_asset(p)
    mi = tools.create_asset("MI_" + name, STORE + "/Instances", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, m)
    a, n, k = tex(d.get("albedo")), tex(d.get("normal"), srgb=False, normal=True), tex(d.get("ms"), srgb=False)
    if a: mel.set_material_instance_texture_parameter_value(mi, "Albedo", a)
    if n: mel.set_material_instance_texture_parameter_value(mi, "Normal", n)
    if k: mel.set_material_instance_texture_parameter_value(mi, "Mask", k)
    rr = d.get("rough_range") or [0.3, 0.85]
    mel.set_material_instance_scalar_parameter_value(mi, "RoughLo", rr[0]); mel.set_material_instance_scalar_parameter_value(mi, "RoughHi", rr[1])
    eal.save_loaded_asset(mi); made[name] = mi
log("store instances", len(made))
# master defaults must match each sampler type (a colour texture in a normal sampler fails to compile): use real ones
for d in SRC.values():
    a, n, k = tex(d.get("albedo")), tex(d.get("normal"), srgb=False, normal=True), tex(d.get("ms"), srgb=False)
    if a and n and k: sp(al, "texture", a); sp(nm, "texture", n); sp(mk, "texture", k); break
mel.recompile_material(m); eal.save_loaded_asset(m)

for i in range(1, 7):
    sm = eal.load_asset("%s/Characters/VikingTiers/SM_Viking_Tier%d" % (DEST, i))
    if not sm: continue
    n = 0
    for j, s in enumerate(sm.get_editor_property("static_materials")):
        slot = str(s.get_editor_property("material_slot_name"))
        key = next((k for k in made if slot == k or slot.startswith(k)), None)
        if key: sm.set_material(j, made[key]); n += 1
    eal.save_loaded_asset(sm); log("SM_Viking_Tier%d store slots:" % i, n)
