import requests

requests.get(url="http://127.0.0.1:7084/")

requests.post(url="http://127.0.0.1:7084/data?data=hello")

requests.post(
    url="http://127.0.0.1:7084/data",
    params={
        "data": "hello"
    }
)

try:
    import traceback
    from UX.info import InfoDialog
    import requests
    from pathlib import Path
    from dotenv import load_dotenv, set_key
    from urllib.parse import parse_qs
    import json
    from flow import menu, login, autosave
    from plugin import Plugin
    from utils.git import Git, find_github_repo, check_user_credentials
    from utils import settings, build, misc
    from github import Auth
    import utils.platform.darwin as darwin
    import os
    from utils.log import log
    import wx
    import time
    import threading
    from concurrent.futures import ThreadPoolExecutor

    env_path = Path(__file__).parent / ".env"
    kicad_path = Path(__file__).parents[4]

    if not env_path.exists():
        with open(".env","x") as env:
            pass
    if not kicad_path.is_dir() or kicad_path.name != "KiCad":
        pass

    load_dotenv(env_path)

    loadUI = InfoDialog(None, "Loading Plugin...", "Initialising (1/5)", "Loading", [])
except Exception as e:
    requests.post(
        "http://127.0.0.1:7084/data",
        params={
            "data": str(e)
        }
    )

@misc.handle
def finish_initialization(git, app, repo):
    if not repo:
        loadUI.update(
            "This is not an SFR Board",
            f"Have you created the board under the SFR/Kicad/Boards/{settings.get('info/car') or 'SFRxx'} folder?",
            "Error"
        )
        loadUI.ShowModal()
        return

    git.set_local_repo(repo)

    expected_path = Path(build.get("github/car_path")) / settings.get("info/car")
    actual_path = Path(app.project.path).parent.relative_to(git.local_root)
    if expected_path != actual_path:
        loadUI.update(
            "This is not an SFR Board",
            f"Have you created the board under the SFR/Kicad/Boards/{settings.get('info/car') or 'SFRxx'} folder?",
            "Error"
        )
    wx.CallAfter(
        loadUI.update, 
        "Loading Plugin...", 
        "Comparing Repo to origin (4/5)", 
        "Loading", 
        []
    )
    if git.outstanding_commits():
        wx.CallAfter(loadUI.update, "You have outstanding commits", "You have 1 or more commits which are not pushed to Github.\nContact your subteam lead to resolve this.You have 1 or more commits which are not pushed to Github.\nContact your subteam lead to resolve this.", "Error")
        loadUI.ShowModal()
        return
    wx.CallAfter(
        loadUI.update, 
        "Loading Plugin...", 
        "Fetching non-modified boards (5/5)", 
        "Loading", 
        []
    )
    git.fetch_latest_boards()
    loadUI.Hide()
    return True

@misc.handle
def initialize():
    wx.CallAfter(
            loadUI.update, 
            "Loading Plugin...", 
            "Verifiying permissions (2/5)", 
            "Loading", 
            []
        )
    login.start(loadUI)
    settings.set("github/login", check_user_credentials())
    # KiCad's IPC client must be used from the action's main thread. Calling
    # it from a worker can race the API server while it is handling this
    # action (and can crash KiCad inside API_HANDLER::Handle).
    app = Plugin()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future_a = executor.submit(Git)
        git = future_a.result()
    wx.CallAfter(
        loadUI.update, 
        "Loading Plugin...", 
        "Finding Repo (3/5)", 
        "Loading", 
        []
    )

    repo = find_github_repo(app.project.path)
    ui = menu.get(git, app)
    if not finish_initialization(git, app, repo):
        return
    autosave.start(git, app)
    ui.show()

@misc.handle
def main():
    log("IPC Button Activated")
    loadUI.show()
    wx.YieldIfNeeded()
    initialize()

main()