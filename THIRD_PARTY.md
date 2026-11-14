# Third-party content

The game uses assets from the sources below. Content that may be redistributed is in this repository; licensed store
content is **not** (see `.gitignore`). To rebuild the full project, download those packs with your own account and
run the scripts noted.

## Included in this repository
| Content | Source | Licence |
|---|---|---|
| MakeHuman skins, eyes, eyebrows, eyelashes, teeth, hair (used for every character) | MakeHuman Community 1.3 / MPFB for Blender | CC0 |
| Gjermundbu helmet reference photo (`models/reference/`) | NTNU Vitenskapsmuseet, via Wikimedia | CC BY 2.0 (see `models/reference/CREDITS.txt`) |

## Not included: re-download these
| Pack | Where | Used for | Rebuild step |
|---|---|---|---|
| Warrior viking with red hair and armor (AgarkovaCG) | Unity Asset Store | Viking tier shirts, tunics, belts, pouches, fur | Extract into `asset_library/unity/Viking_Warrior_AgarkovaCG`, then run `blender/viking_armor_tiers.py` |
| Viking Shields pack, Viking Swords pack (FunFant) | Unity Asset Store | Tier shields and swords | Extract into `asset_library/unity/` |
| Realistic Battle Axe (Snake3D) | Unity Asset Store | Tier 3 axe | Extract into `asset_library/unity/` |
| Medieval Weapons PBR Pack (Bek) | Unity Asset Store | Spear, hatchet | Extract into `asset_library/unity/` |
| Seven Swords V2 (Perpetual Diversion) | Unity Asset Store / Fab | Ulfberht sword | Extract into `asset_library/unity/` |
| Medieval Village Megascans Sample | Fab (Quixel Megascans) | Village and environment | Create the project from the Epic launcher, copy its `Content` into `Unreal/ShatteredLands/Content` |
| MetaHumans | Fab (Epic Games) | Photoreal human tests | Create the project from the Epic launcher, copy its `Content` into `Unreal/ShatteredLands/Content` |
| Third Person template content (mannequin, input, level prototyping) | Unreal Engine 5.8 | Player character and controls | `unreal_tools/setup_project.ps1` copies it from the engine |

Unity extraction: the `.unitypackage` cache is in `%APPDATA%\Unity\Asset Store-5.x`. Each package is a tar.gz in which
every GUID folder holds an `asset` file and its original `pathname`.

The full list of free Fab packs that were evaluated is in `asset_library/FAB_FREE_MEDIEVAL_PACKS.md`.
