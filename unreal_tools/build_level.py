"""
Unreal 5.8 editor Python (run inside the full editor: UnrealEditor.exe <uproject> -ExecutePythonScript=build_level.py).
Builds /Game/ShatteredLands/Maps/BattleTest as a fresh level with sun, sky atmosphere, sky light, fog, clouds and a
player start; lays the 20 m battlefield patch as a 5 x 5 mirrored ground, places the animated
Viking and the 12 tier soldiers (English row facing Viking row), saves, then takes editor screenshots and quits.
Screenshots land in <project>/Saved/Screenshots/. Lines starting with SL_ are progress markers.
"""
import unreal, time

DEST = "/Game/ShatteredLands"; MAP = DEST + "/Maps/BattleTest"; SRC = "/Game/ThirdPerson/Lvl_ThirdPerson"
eal = unreal.EditorAssetLibrary
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)


def log(*a): unreal.log_warning("SL_ " + " ".join(str(x) for x in a))


def sp(obj, name, val):
    """Set a property if this engine version has it (names shift between UE releases)."""
    try: obj.set_editor_property(name, val)
    except Exception as e: log("property skipped:", name)


def asset(path):
    return eal.load_asset(path) if eal.does_asset_exist(path) else None


def find(folder, cls):
    out = []
    for p in eal.list_assets(folder, recursive=True, include_folder=False):
        a = eal.load_asset(p)
        if isinstance(a, cls): out.append(a)
    return out


if eal.does_asset_exist(MAP): les.load_level(MAP)
else:
    ok = False
    try: ok = les.new_level(MAP, False)        # plain (non-World-Partition) level; fine for a test battlefield
    except TypeError: ok = les.new_level(MAP)
    log("new_level returned", ok)
world = ues.get_editor_world()
if not world or world.get_path_name().split(".")[0] != MAP:
    raise RuntimeError("SL_ refusing to build: current level is %s, not %s" % (world.get_path_name() if world else None, MAP))
for a in eas.get_all_level_actors():                  # rebuilding: clear our own previous contents
    if a.get_class().get_name() not in ("WorldSettings", "Brush", "WorldDataLayers"): eas.destroy_actor(a)

# outdoor lighting: physical sun + sky atmosphere, real-time sky light, height fog, clouds; autumn morning angle
def spawn(cls, loc=(0, 0, 0), rot=(0, 0, 0), label=None):
    a = eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(*rot))
    if label: a.set_actor_label(label)
    a.set_folder_path("Lighting"); return a
sun = spawn(unreal.DirectionalLight, (0, 0, 1000), (0, -28, 35), "Sun")
sc = sun.get_component_by_class(unreal.DirectionalLightComponent)
sp(sc, "intensity", 9.0); sp(sc, "atmosphere_sun_light", True)
sp(sc, "light_color", unreal.Color(255, 236, 214, 255)); sp(sc, "mobility", unreal.ComponentMobility.MOVABLE)
spawn(unreal.SkyAtmosphere, label="SkyAtmosphere")
sky = spawn(unreal.SkyLight, (0, 0, 500), label="SkyLight")
skc = sky.get_component_by_class(unreal.SkyLightComponent)
sp(skc, "real_time_capture", True); sp(skc, "mobility", unreal.ComponentMobility.MOVABLE)
fog = spawn(unreal.ExponentialHeightFog, label="HeightFog")
fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent); sp(fc, "fog_density", 0.02)
sp(fc, "volumetric_fog", True)
spawn(unreal.VolumetricCloud, label="Clouds")
spawn(unreal.PlayerStart, (0, -900, 120), (0, 0, 90), "PlayerStart")
log("fresh level with sky, sun, fog, clouds")

# battlefield ground: the baked 20 m patch tiled 5 x 5, alternate tiles mirrored so the edges meet seamlessly
# (mirrored variants are real geometry exported from Blender: negative actor scale breaks normal-map lighting)
tiles = {(0, 0): "", (1, 0): "_MX", (0, 1): "_MY", (1, 1): "_MXY"}
for gx in range(-2, 3):
    for gy in range(-2, 3):
        ground = asset(DEST + "/Terrain/SM_TerrainPatch_20m" + tiles[(gx % 2, gy % 2)]) or asset(DEST + "/Terrain/SM_TerrainPatch_20m")
        g = eas.spawn_actor_from_object(ground, unreal.Vector(gx * 2000.0, gy * 2000.0, 0.0))
        g.set_actor_label("Ground_%d_%d" % (gx, gy)); g.set_folder_path("Battlefield")

# animated Viking warrior (idle loop) front and centre
skm = asset(DEST + "/Characters/Viking/SK_Viking_Warrior")
idle = asset(DEST + "/Characters/Viking/SK_Viking_WarriorArmature_idle")
if skm:
    v = eas.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 180))   # imported models face +Y; turn to face the camera (-Y)
    comp = v.skeletal_mesh_component
    try: comp.set_skinned_asset_and_update(skm)
    except Exception: comp.set_editor_property("skeletal_mesh", skm)
    if idle:
        comp.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        pd = unreal.SingleAnimationPlayData(); pd.set_editor_property("anim_to_play", idle); pd.set_editor_property("saved_looping", True); pd.set_editor_property("saved_playing", True)
        comp.set_editor_property("animation_data", pd)
    v.set_actor_label("Viking_Warrior_Animated"); v.set_folder_path("Soldiers")

# tier lineups: English along -X side facing +X, Vikings along +X side facing -X
for side, folder, prefix, x, yaw in (("English", "English", "SM_English_Tier", -350.0, -90.0), ("Viking", "VikingTiers", "SM_Viking_Tier", 350.0, 90.0)):
    for i in range(1, 7):
        m = asset("%s/Characters/%s/%s%d" % (DEST, folder, prefix, i))
        if not m: continue
        a = eas.spawn_actor_from_object(m, unreal.Vector(x, (i - 3.5) * 230.0, 0.0), unreal.Rotator(0, 0, yaw))
        a.set_actor_label("%s_Tier%d" % (side, i)); a.set_folder_path("Soldiers/" + side)
# the hero Gjermundbu helmet (multi-part glTF) on a wooden display post beside the Viking
STAND = unreal.Vector(-170.0, -60.0, 0.0); TOP = 112.0
post = eas.spawn_actor_from_object(asset("/Engine/BasicShapes/Cylinder"), STAND + unreal.Vector(0, 0, TOP / 2))
post.set_actor_scale3d(unreal.Vector(0.22, 0.22, TOP / 100.0)); post.set_actor_label("Helmet_Stand"); post.set_folder_path("Props")
wood = next((a for a in find(DEST + "/Materials/Instances", unreal.MaterialInstanceConstant) if "Shaft" in a.get_name() or "Wood" in a.get_name()), None)
if wood: post.static_mesh_component.set_material(0, wood)
parts = [eas.spawn_actor_from_object(p, unreal.Vector(0, 0, 0)) for p in find(DEST + "/Props", unreal.StaticMesh)]
if parts:
    # move the parts together as one group: same offset for all, so each keeps its place relative to the bowl
    lo = min(a.get_actor_bounds(False)[0].z - a.get_actor_bounds(False)[1].z for a in parts)
    bowl = next((a for a in parts if "Bowl" in a.get_actor_label()), parts[0]); bc = bowl.get_actor_bounds(False)[0]
    delta = unreal.Vector(STAND.x - bc.x, STAND.y - bc.y, TOP - lo)
    for a in parts:
        a.set_actor_location(a.get_actor_location() + delta, False, False)
        a.set_actor_label("Gjermundbu_" + a.get_actor_label()); a.set_folder_path("Props/Gjermundbu_Helmet")
    log("helmet parts placed:", len(parts))

les.save_current_level()
# World Partition levels keep each actor in its own package (__ExternalActors__): save every dirty package too
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
log("level saved", MAP, "actors:", len(eas.get_all_level_actors()))

# ---- screenshots: let shaders compile and the viewport settle, then frame each view and capture
VIEWS = [("overview", unreal.Vector(-1500, -1500, 650), unreal.Rotator(0, -16, 45)),
         ("viking_close", unreal.Vector(-10, -260, 170), unreal.Rotator(0, -4, 90)),
         ("english_row", unreal.Vector(-900, 0, 220), unreal.Rotator(0, -6, 0)),
         ("viking_row", unreal.Vector(900, 0, 220), unreal.Rotator(0, -6, 180))]
state = {"t0": time.time(), "i": -1, "next": 0.0}


def tick(dt):
    now = time.time() - state["t0"]
    if now < 75: return                                           # first-open shader compile
    if now < state["next"]: return
    i = state["i"]
    if i >= 0: log("screenshot requested", VIEWS[i][0])
    i += 1; state["i"] = i
    if i < len(VIEWS):
        name, loc, rot = VIEWS[i]
        ues.set_level_viewport_camera_info(loc, rot)
        unreal.SystemLibrary.execute_console_command(None, "HighResShot 1600x900 filename=SL_%s" % name)
        state["next"] = now + 12
    elif now > state["next"] + 8:
        log("done; quitting"); unreal.unregister_slate_post_tick_callback(handle); unreal.SystemLibrary.quit_editor()


handle = unreal.register_slate_post_tick_callback(tick)
