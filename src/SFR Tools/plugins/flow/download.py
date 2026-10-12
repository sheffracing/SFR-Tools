import traceback
from pathlib import Path
import time

import wx
from dotenv import load_dotenv

from UX.download import DownloadDialog
from plugin import Plugin
from utils import build, settings, misc
from utils.git import Git, NoChanges
from utils.log import log
from utils.platform import darwin, win32

env_path = Path(__file__).parents[1] / ".env"

load_dotenv(env_path)

@misc.handle
def __pull(self, event):
    github: Git = self.parent.git
    plugin: Plugin = self.parent.plugin
    
    response_darwin = darwin.modal("This might overwrite data", "Are you sure you want to overwrite this board? This action cannot be undone.", ("Go Back", "Overwrite"))
    response_win32 = win32.modal("This might overwrite data", "Are you sure you want to overwrite this board? This action cannot be undone.", ("No", "Yes"))
    if (response_darwin or response_win32) == 0:
         return
    else:
        board = Path(build.get("github/car_path")) / settings.get("info/car") / self.current_board
        source = github.get_full_commit_sha(self.current_commit.split(None, 1)[0]) if self.current_commit else f"origin/{self.current_branch}"
        board_open = Path(plugin.project.path).name == board.name
        try:
            wx.BeginBusyCursor()
            if board_open:
                 plugin.Save()
                 plugin.quit(True)
            github.prune_deleted_branches()
            branches = github.find_branches_for_directory(board)

            try:
                if len(branches) == 1:
                     github.restore_board(board,branches[0],source)
                else:
                    github.pull_board(board,source)
            except NoChanges:
                 pass

            if board_open:
                time.sleep(0.5)
                plugin.open(plugin.project.path, True, True)
        except Exception as e:
             log(traceback.format_exc())
        finally:
             wx.BeginBusyCursor()
             wx.CallAfter(self.EndModal, wx.ID_OK)
             wx.CallAfter(self.parent.EndModal, wx.ID_OK)


@misc.handle
def __get_branches(self, board, event = None):
    github: Git = self.parent.git
    plugin: Plugin = self.parent.plugin

    branches = github.find_branches_for_directory(Path(build.get("github/car_path")) / settings.get("info/car") / self.current_board)
    branches.insert(0,"main") 
    return branches

@misc.handle
def __get_commits(self, branch, event = None):
    github: Git = self.parent.git
    plugin: Plugin = self.parent.plugin

    commits = []
    for commit in github.get_branch_commits(branch):
        commits.append(f"{commit.hexsha[:7]} ({commit.message.splitlines()[0]})")
    return commits

@misc.handle
def get(menu):
    callbacks = {
        "pull": __pull,
        "get_branches": __get_branches,
        "get_commits": __get_commits
    }
    data = {
        "boards": menu.git.get_boards()
    }
    ui = DownloadDialog(menu, callbacks=callbacks, data=data)
    ui.show()
    return ui
