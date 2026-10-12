import traceback
from pathlib import Path
import wx
from dotenv import load_dotenv

from UX.save import Save
from plugin import Plugin
from utils.git import Git
from utils.log import log
from utils import misc
import utils.platform.darwin as darwin

env_path = Path(__file__).parents[1] / ".env"

load_dotenv(env_path)

@misc.handle
def __success(self, summary: str, description: str):
    github: Git = self.parent.git
    plugin: Plugin = self.parent.plugin
    try:
        plugin.Save()
        github.commit_branch(Path(plugin.project.path), plugin.branch_name, summary, description)
        #github.push_branch(plugin.branch_name)
        self.EndModal(wx.ID_CLOSE)
        return True, {}
    except Exception as e:
        log(f"e: {traceback.format_exc()}")
        success = False
        data = {"error": e, "traceback": traceback.format_exc()}
        return success, data

@misc.handle
def get(menu):
    try:
        callbacks = {
            "success": __success,
        }
        ui = Save(menu, callbacks=callbacks)
        response = ui.show()
    except Exception as e:
        log(traceback.format_exc())
    return ui
