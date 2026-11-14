# Shattered Lands — A Viking Saga

A Viking-age campaign and 3D battle game in the Mount & Blade genre: England, 865, the Great Heathen Army. It began as
a single-file browser game (three.js) and is being ported to **Unreal Engine 5.8**.

## What's here
| Path | Contents |
|---|---|
| `index.html` | The playable browser version: campaign map, warbands, economy, sieges, beach landings, 3D battles |
| `blender/` | Blender 5.x scripts for every character and asset: MakeHuman (MPFB) soldiers, armour tiers 1–6 (Viking and English), the Gjermundbu helmet, battlefield terrain, the exporter to Unreal (`export_unreal.py`), and the store-gear fitter (`warrior_gear.py`) |
| `unreal_tools/` | Unreal editor Python and PowerShell: project setup, asset import, materials (skin, hair, box-mapped cloth/mail/steel, terrain), the test battlefield level, automated screenshots |
| `Unreal/ShatteredLands/` | The Unreal 5.8 project (config and the `Content/ShatteredLands` folder) |
| `unreal_export/` | FBX / heightmap / texture kit exported from Blender for Unreal |
| `models/` | Blender scenes, renders and textures |
| `asset_library/` | Notes on third-party asset sources |

## Rebuilding the Unreal project
1. Install Unreal Engine 5.8, Blender 5.x with the MPFB add-on, and MakeHuman Community 1.3 (for its CC0 assets).
2. `powershell -ExecutionPolicy Bypass -File unreal_tools\setup_project.ps1` creates the project from the Third
   Person template and imports the export kit.
3. Run `unreal_tools/materials.py`, `surface_materials.py` and `store_materials.py` with the PythonScript commandlet,
   then `build_level.py` in the editor (see the docstrings).
4. Third-party store packs aren't in the repository; `THIRD_PARTY.md` lists them and where they go.
