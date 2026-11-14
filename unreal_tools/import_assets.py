"""
Unreal 5.8 editor Python: imports the Blender export kit (../unreal_export) into /Game/ShatteredLands and builds a
test level with the battlefield ground, the animated Viking and the 12 tier soldiers in a lineup.
Run by setup_project.ps1 through the PythonScript commandlet; safe to re-run (re-imports replace assets).
Lines starting with SL_ are progress markers.
"""
import os, json
import unreal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "unreal_export"))
DEST = "/Game/ShatteredLands"
tools = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary


def log(*a): unreal.log("SL_ " + " ".join(str(x) for x in a)); print("SL_", *a)


def sp(obj, name, val):
    """Set an import option if this engine version has it (names shift between UE releases)."""
    try: obj.set_editor_property(name, val)
    except Exception as e: log("option skipped:", name, e)


def fbx_task(src, dest, skeletal=False, anims=False, combine=True):
    ui = unreal.FbxImportUI()
    for k, v in (("import_mesh", True), ("import_materials", True), ("import_textures", True), ("import_as_skeletal", skeletal),
                 ("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH),
                 ("import_animations", anims), ("create_physics_asset", skeletal), ("automated_import_should_detect_type", False)):
        sp(ui, k, v)
    sm = ui.get_editor_property("static_mesh_import_data")
    for k, v in (("combine_meshes", combine), ("generate_lightmap_u_vs", True), ("auto_generate_collision", True)): sp(sm, k, v)
    sp(ui.get_editor_property("texture_import_data"), "material_search_location", unreal.MaterialSearchLocation.LOCAL)
    t = unreal.AssetImportTask(); t.filename = src; t.destination_path = dest
    t.automated = True; t.save = True; t.replace_existing = True; t.options = ui
    return t


def plain_task(src, dest):
    t = unreal.AssetImportTask(); t.filename = src; t.destination_path = dest; t.automated = True; t.save = True; t.replace_existing = True
    return t


def run(tasks):
    tools.import_asset_tasks(tasks)
    out = []
    for t in tasks: out += list(t.imported_object_paths or [])
    return out


# ---------------------------------------------------------------- characters
viking = run([fbx_task(os.path.join(ROOT, "Characters", "Viking", "SK_Viking_Warrior.fbx"), DEST + "/Characters/Viking", skeletal=True, anims=True)])
log("viking", len(viking), "assets:", [p.split(".")[-1] for p in viking])
tiers = []
for side, folder, prefix in (("English", "English", "SM_English_Tier"), ("Viking", "VikingTiers", "SM_Viking_Tier")):
    for i in range(1, 7):
        src = os.path.join(ROOT, "Characters", folder, "%s%d.fbx" % (prefix, i))
        if os.path.exists(src): tiers.append((side, i, run([fbx_task(src, DEST + "/Characters/" + folder)])))
log("tiers imported", len(tiers))

# ---------------------------------------------------------------- terrain + props + textures
ter = run([fbx_task(os.path.join(ROOT, "Terrain", "SM_TerrainPatch_20m.fbx"), DEST + "/Terrain")])
tex = run([plain_task(os.path.join(ROOT, "Terrain", "Textures", f), DEST + "/Terrain/Textures") for f in os.listdir(os.path.join(ROOT, "Terrain", "Textures"))])
tex += run([plain_task(os.path.join(ROOT, "Terrain", "T_TerrainPatch_Height_505.png"), DEST + "/Terrain")])
for p in tex:
    a = eal.load_asset(p)
    if not isinstance(a, unreal.Texture2D): continue
    n = a.get_name().lower()
    if "normal" in n: a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP); a.set_editor_property("srgb", False)
    if "rough" in n or "height" in n: a.set_editor_property("srgb", False)
    if "height" in n: a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    eal.save_loaded_asset(a)
helm = run([plain_task(os.path.join(ROOT, "Props", "SM_Gjermundbu_Helmet.glb"), DEST + "/Props")])
log("terrain", len(ter), "textures", len(tex), "props", len(helm))

log("import done")
