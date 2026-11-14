# Prints every actor in a level with class, location/rotation and key light settings, then quits (SL_INSPECT=1 hook).
import unreal, os
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem); eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.load_level(os.environ.get("SL_MAP") or "/Game/ShatteredLands/Maps/BattleTest")
counts = {}
for a in eas.get_all_level_actors():
    cn = a.get_class().get_name(); counts[cn] = counts.get(cn, 0) + 1
    if cn in ("DirectionalLight", "SkyLight", "SkyAtmosphere", "ExponentialHeightFog", "VolumetricCloud", "PlayerStart", "PostProcessVolume"):
        extra = ""
        for comp_cls in (unreal.LightComponent, unreal.SkyLightComponent):
            c = a.get_component_by_class(comp_cls)
            if c:
                for k in ("intensity", "mobility", "atmosphere_sun_light", "real_time_capture", "visible", "affects_world"):
                    try: extra += " %s=%s" % (k, c.get_editor_property(k))
                    except Exception: pass
        unreal.log_warning("SL_ACTOR %s loc=%s rot=%s hidden=%s%s" % (cn, a.get_actor_location(), a.get_actor_rotation(), a.is_hidden_ed(), extra))
unreal.log_warning("SL_COUNTS %s" % counts)
unreal.SystemLibrary.quit_editor()
