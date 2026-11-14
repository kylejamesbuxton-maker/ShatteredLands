# Project editor startup hook (registered in Config/DefaultEngine.ini). Does nothing unless SL_AUTOSHOT=1 is set,
# in which case it runs screenshots.py (open BattleTest, capture views, quit) for automated visual checks.
import os, runpy
if os.environ.get("SL_AUTOSHOT") == "1":
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots.py"), run_name="__main__")

if os.environ.get("SL_INSPECT") == "1":
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "inspect_level.py"), run_name="__main__")
