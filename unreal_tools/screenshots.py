"""
Unreal editor Python: opens /Game/ShatteredLands/Maps/BattleTest, places a camera per view, starts Play-In-Editor,
switches the player's view to each camera and takes HighResShot screenshots, then stops play and quits.
Images land in <project>/Saved/Screenshots/WindowsEditor/ as SL_<view>.png.
Started by editor_startup.py when SL_AUTOSHOT=1 (the -ExecutePythonScript flag quits the editor immediately).
"""
import unreal, time, os

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.load_level(os.environ.get("SL_MAP") or "/Game/ShatteredLands/Maps/BattleTest")


def log(*a): unreal.log_warning("SL_ " + " ".join(str(x) for x in a))


VIEWS = [("overview", unreal.Vector(-1500, -1500, 650), unreal.Rotator(0, -16, 45)),
         ("viking_close", unreal.Vector(0, -230, 165), unreal.Rotator(0, -3, 90)),
         ("viking_face", unreal.Vector(0, -85, 168), unreal.Rotator(0, -2, 90)),
         ("english_row", unreal.Vector(-1000, 0, 200), unreal.Rotator(0, -5, 0)),
         ("viking_row", unreal.Vector(1000, 0, 200), unreal.Rotator(0, -5, 180)),
         ("helmet", unreal.Vector(-170, -175, 130), unreal.Rotator(0, -8, 90)),
         ("english_close", unreal.Vector(-350, -330, 150), unreal.Rotator(0, -4, 72)),
         ("viking_t3", unreal.Vector(135, -115, 150), unreal.Rotator(0, -3, 0)),
         ("viking_t4_5", unreal.Vector(-60, 230, 160), unreal.Rotator(0, -4, 0)),
         ("viking_t6", unreal.Vector(135, 575, 150), unreal.Rotator(0, -3, 0))]
if os.environ.get("SL_MAP") and "BattleTest" not in os.environ.get("SL_MAP"):
    # any other map: frame views around its PlayerStart (cameras must sit near the player so World Partition loads them)
    ps = next((a for a in eas.get_all_level_actors() if isinstance(a, unreal.PlayerStart)), None)
    p = ps.get_actor_location() if ps else unreal.Vector(0, 0, 200); yaw = ps.get_actor_rotation().yaw if ps else 0.0
    def look(frm, to):
        d = to - frm; return unreal.MathLibrary.make_rot_from_x(d)
    VIEWS = [("map_overview", p + unreal.Vector(-1600, -1600, 1100), look(p + unreal.Vector(-1600, -1600, 1100), p + unreal.Vector(0, 0, 100))),
             ("map_street", p + unreal.Vector(0, 0, 60), unreal.Rotator(0, -2, yaw)),
             ("map_street_back", p + unreal.Vector(0, 0, 60), unreal.Rotator(0, -2, yaw + 180)),
             ("map_high", p + unreal.Vector(600, 600, 700), look(p + unreal.Vector(600, 600, 700), p + unreal.Vector(-1500, -1500, 0)))]
cams = []
for name, loc, rot in VIEWS:
    c = eas.spawn_actor_from_class(unreal.CameraActor, loc, rot); c.set_actor_label("SLCam_" + name)
    cc = c.get_component_by_class(unreal.CameraComponent); cc.set_editor_property("field_of_view", 55.0)
    try: cc.set_editor_property("constrain_aspect_ratio", False)
    except Exception: pass
    cams.append(c)
les.editor_request_begin_play()
S = {"t0": time.time(), "i": -1, "at": 0.0, "stage": "wait_pie"}


def game_cam(gw, name):
    for a in unreal.GameplayStatics.get_all_actors_of_class(gw, unreal.CameraActor):
        if a.get_actor_label() == "SLCam_" + name: return a
    return None


def tick(dt):
    now = time.time() - S["t0"]
    if now < S["at"]: return
    gw = ues.get_game_world()
    if S["stage"] == "wait_pie":
        if gw is None:
            if now > 1500: log("PIE never started"); finish()
            return
        S["stage"] = "shoot"; S["at"] = now + 25; log("PIE running"); return       # let shaders/streaming settle
    if S["stage"] == "shoot":
        S["i"] += 1
        if S["i"] >= len(VIEWS): S["stage"] = "end"; S["at"] = now + 6; return
        name = VIEWS[S["i"]][0]; pc = unreal.GameplayStatics.get_player_controller(gw, 0); cam = game_cam(gw, name)
        if pc and cam:
            pc.set_view_target_with_blend(cam, 0.0)
            S["pending"] = name; S["stage"] = "capture"; S["at"] = now + 3
        else: log("no camera/controller for", name)
        return
    if S["stage"] == "capture":
        unreal.SystemLibrary.execute_console_command(gw, "HighResShot 1600x900 filename=SL_%s" % S["pending"])
        log("shot", S["pending"]); S["stage"] = "shoot"; S["at"] = now + 4; return
    if S["stage"] == "end": finish()


def finish():
    unreal.unregister_slate_post_tick_callback(H)
    try: les.editor_request_end_play()
    except Exception: pass
    for c in cams:
        try: eas.destroy_actor(c)
        except Exception: pass
    log("done"); unreal.SystemLibrary.quit_editor()


H = unreal.register_slate_post_tick_callback(tick)
log("starting play-in-editor")
