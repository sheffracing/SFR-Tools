import traceback
from pathlib import Path
import wx
from dotenv import load_dotenv

from UX.info import InfoDialog
from UX.review import Review
from flow import autosave
from plugin import Plugin
from utils import misc
from utils.git import Git
from utils.log import log

env_path = Path(__file__).parents[1] / ".env"

load_dotenv(env_path)

@misc.handle
def __success(self, description: str):
    github: Git = self.parent.git
    plugin: Plugin = self.parent.plugin

    autosave.run(github, plugin)
    url = github.make_pr(
        Path(plugin.project.path),
        plugin.branch_name,
        description,
        plugin.get_version(),
        True
    )
    wx.LaunchDefaultBrowser(url)
    self.EndModal(wx.ID_CLOSE)
    ui = InfoDialog(None, "Success", "Your Pull Request (PR) has been created","Success")
    end = ui.show(True)

@misc.handle
def get(menu):
    github: Git = menu.git
    plugin: Plugin = menu.plugin

    if github.pr_exists(plugin.branch_name):
        ui = InfoDialog(None, "Pull Request already exists", f"A pull request already exists for {plugin.branch_name}.", "Info", [("Open PR", wx.ID_OPEN), ("Check Validity", wx.ID_OK), ("Close", wx.ID_CLOSE)])
        response = ui.show(True)
        if response == wx.ID_OPEN:
            wx.LaunchDefaultBrowser(github.get_pr_url(plugin.branch_name))
        elif response == wx.ID_OK:
            url = github.make_pr(
                Path(plugin.project.path),
                plugin.branch_name,
                None,
                plugin.get_version(),
                True
            )
            wx.LaunchDefaultBrowser(url)
        return None
    
    callbacks = {
        "success": __success,
    }
    ui = Review(menu, callbacks=callbacks)
    response = ui.show()
