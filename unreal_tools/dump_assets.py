import unreal
eal = unreal.EditorAssetLibrary
tex = [p for p in eal.list_assets("/Game/ShatteredLands", recursive=True) if isinstance(eal.load_asset(p), unreal.Texture2D)]
unreal.log_warning("SL_TEX %d %s" % (len(tex), [p.split(".")[-1] for p in tex][:40]))
for p in ["/Game/ShatteredLands/Characters/Viking/SK_Viking_Warrior", "/Game/ShatteredLands/Characters/English/SM_English_Tier1", "/Game/ShatteredLands/Terrain/SM_TerrainPatch_20m"]:
    a = eal.load_asset(p)
    mats = a.get_editor_property("materials") if isinstance(a, unreal.SkeletalMesh) else a.get_editor_property("static_materials")
    unreal.log_warning("SL_MESH %s %s" % (p.split("/")[-1], [(m.get_editor_property("material_slot_name"), m.get_editor_property("material_interface").get_name() if m.get_editor_property("material_interface") else None) for m in mats]))
    if isinstance(a, unreal.StaticMesh): unreal.log_warning("SL_BOUNDS %s %s" % (p, a.get_bounds().box_extent))
for p in eal.list_assets("/Game/ShatteredLands/Props", recursive=True):
    a = eal.load_asset(p)
    if isinstance(a, unreal.StaticMesh): unreal.log_warning("SL_PROP %s extent=%s" % (p, a.get_bounds().box_extent))
