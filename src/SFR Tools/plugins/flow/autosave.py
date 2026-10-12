import threading
import time
import traceback
from pathlib import Path

import wx
from dotenv import load_dotenv

from UX.info import InfoDialog
from plugin import Plugin
from utils import settings
from utils.git import Git, NoChanges
from utils.log import log
from utils.platform import darwin, win32 as win

env_path = Path(__file__).parents[1] / ".env"

load_dotenv(env_path)


def worker(interval: int, func):
    def wrapper(github: Git, plugin: Plugin, *args,**kwargs):
        while plugin.isConnected():
            func(github, plugin, *args,**kwargs)
            time.sleep(interval*60)
    return wrapper

def run(github: Git, plugin: Plugin):
    try:
        plugin.Save()
        time.sleep(0.1)
        github.commit_branch(Path(plugin.project.path), plugin.branch_name, "Autosave", f"This action was performed automatically by SFR Tools.")
    except NoChanges:
        log("No changes detected when autosaving")
    except Exception as e:
        try:
            ui = InfoDialog(None, "An unhandled exception has occured while Autosaving.", str(e),"Error", True, None)
            end = ui.show()
        except:
            log(traceback.format_exc())
        if end == wx.ID_RETRY:
            return run(github, plugin)

def start(github: Git, plugin: Plugin):
    try:
        thread = threading.Thread(target=worker(settings.get("info/autosave/interval"),run),daemon=True, args=(github, plugin))
        thread.start()
    except Exception as e:
        log(traceback.format_exc())

def get(menu):
    start(menu.git, menu.plugin)
