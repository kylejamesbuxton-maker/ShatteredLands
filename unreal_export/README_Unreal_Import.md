# Shattered Lands — Unreal Engine 5.8 import kit

Everything here was exported from the Blender project by `blender/export_unreal.py`. Units are real-world
(metres in Blender, centimetres in Unreal). Characters face −Y in Blender, which becomes +X forward in Unreal.

## Characters/Viking/SK_Viking_Warrior.fbx — rigged, animated
- Contains the MakeHuman Viking with skin, eyes, brows, lashes, hair and the shell-fur beard. He wears a tunic,
  trousers, boots, belt, mail, a helmet, a sword and a shield.
- 53-bone skeleton (MPFB "game_engine" rig: `Root`, `pelvis`, `spine_01..03`, fingers, and so on). 1.85 m tall.
- 5 animations: **idle, walk, guard, over** (overhead swing) and **diag** (diagonal swing).
- Import: drag into the Content Browser.
  - Set *Skeletal Mesh* on, *Import Animations* on, and *Import Uniform Scale* to 1.0.
  - Set *Material Import Method* to *Create New Materials*.
  - The animations import as Anim Sequences named `Armature|<clip>`; rename them.
- Separate textures are in `Textures/` in case Unreal doesn't pick up the embedded ones.
- Later: retarget onto the UE5 Mannequin (IK Retargeter) to use Unreal's animation library. Mail and helmet are
  separate mesh parts, so armour tiers can be swapped per soldier.

## Characters/English/SM_English_Tier1..6.fbx, Characters/VikingTiers/SM_Viking_Tier1..6.fbx
- Six English tiers (fyrdman to Tudor guard) and six Viking tiers (thrall to jarl). Each is a MakeHuman man with
  body-fitted clothing, armour, weapons and (for the Vikings) a round shield.
- These are **posed static meshes**: showcase and reference models, not rigged yet.
- Import as *Static Mesh*. Leave *Combine Meshes* off to keep each armour piece separate.
- The next step for the game is to rebuild them on the rigged Viking skeleton, as was done for SK_Viking_Warrior.

## Terrain
- `T_TerrainPatch_Height_505.png`: 16-bit greyscale heightmap of the 20 m battlefield ground patch.
  - In *Landscape mode → Import from File*, choose this file at 505 × 505.
  - Set the Landscape scale to **X 3.9683, Y 3.9683, Z 32.7414**. These values are also in the `.json`, and they
    give the true 20 m size and 1.68 m height range.
  - For a whole battlefield, tile the patch or sculpt a larger map and use the patch's material.
- `Textures/T_Terrain_Albedo.jpg`, `T_Terrain_Normal.jpg`, `T_Terrain_Roughness.jpg`: the baked ground surface
  (dirt, ruts, cracks, dead grass). Set the normal texture's *Compression* to *Normalmap* and the roughness
  texture's *sRGB* off.
- `SM_TerrainPatch_20m.fbx`: the same patch as a dense static mesh, for close-up set dressing.

## Props/SM_Gjermundbu_Helmet.glb
- Hero Gjermundbu helmet. Unreal 5.8 imports glTF directly; drag it in.

## Source/ShatteredLands_reference.html
- The full browser game: campaign map, warbands, economy, battle AI, combat timing, shields and textures.
- It is the reference for rebuilding the game logic in Unreal C++/Blueprints.

## Recommended Unreal project settings
- Lumen global illumination and reflections on, Nanite on for static props and terrain meshes, Virtual Shadow Maps.
- For skin: use the *Subsurface Profile* shading model on the skin material, with the MakeHuman skin texture as Base Color.
