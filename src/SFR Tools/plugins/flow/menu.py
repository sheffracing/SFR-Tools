
from pathlib import Path
import json
from utils import misc
from UX.menu import MainMenu

tools_path = Path(__file__).parents[1] / "data" / "tools.json"
with open(tools_path,"rt") as file:
    tools = json.load(file)

@misc.handle
def get(git, plugin):
    return MainMenu(None, tools["Menu"], git, plugin)
