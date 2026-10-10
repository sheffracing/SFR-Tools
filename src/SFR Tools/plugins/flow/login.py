import requests
import traceback
from pathlib import Path
from dotenv import set_key
import os
import wx
import threading

from utils.git import check_user_credentials
from utils.log import log
from utils import build, misc

from UX.login import LoiginDialog
from UX.info import InfoDialog

env_path = Path(__file__).parents[1] / ".env"

stop_event = threading.Event()
success_event = threading.Event()


@misc.handle
def generate_code() -> tuple[str, int, str]:
    response = requests.post(
        "https://github.com/login/device/code",
        headers = {
            "Accept": "application/json"
        },
        params = {
            "client_id": build.get("github/client_id")
        }
    )
    if response.status_code != 200:
        ui = InfoDialog(None, "GitHub API Exception", f"HTTP {response.status_code} Exception: {response.text}", "Error")
        ui.show(True)
        return "ERROR", None, None
    params = response.json()
    set_key(env_path, key_to_set="DEVICE_CODE", value_to_set=params["device_code"])
    set_key(env_path, key_to_set="INTERVAL", value_to_set=str(params["interval"]))

    os.environ["DEVICE_CODE"] = params["device_code"]
    os.environ["INTERVAL"] = str(params["interval"])
    return params["user_code"], params["interval"], params["verification_uri"]

@misc.handle
def poll(ui):
    response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers = {
            "Accept": "application/json"
        },
        params = {
            "client_id": build.get("github/client_id"),
            "device_code": os.environ.get("DEVICE_CODE"),
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
        },
        timeout=20
    )

    if response.status_code != 200:
        message = f"HTTP {response.status_code} Exception: {response.text}"
        wx.CallAfter(_show_error, ui, "GitHub API Exception", message)
        stop_event.set()
        return

    params = response.json()
    if "access_token" in params:
        token = params["access_token"]
        set_key(env_path, key_to_set="ACCESS_TOKEN", value_to_set=token)
        os.environ["ACCESS_TOKEN"] = token

        wx.CallAfter(_show_success, ui)
        stop_event.set()
        success_event.set()
        return

    if params.get("error") == "slow_down":
        interval = params.get("interval") or os.environ.get("INTERVAL") or "5"
        set_key(env_path, key_to_set="INTERVAL", value_to_set=str(interval))
        os.environ["INTERVAL"] = str(interval)
    else:
        interval = int(os.environ.get("INTERVAL") or "5")

    if params.get("error") not in (None, "authorization_pending", "slow_down"):
        wx.CallAfter(_show_error, ui, "GitHub Login Failed", params.get("error_description", params["error"]))
        stop_event.set()
        return
    stop_event.wait(interval)

@misc.handle
def _show_error(login_dialog, title, message):
    if login_dialog.IsModal():
        login_dialog.EndModal(wx.ID_CANCEL)
    dialog = InfoDialog(None, title, message, "Error")
    dialog.show(True)


@misc.handle
def _show_success(login_dialog):
    if login_dialog.IsModal():
        login_dialog.EndModal(wx.ID_OK)
    dialog = InfoDialog(None, "Success!", "You have successfully logged in", "Success", [("Continue", wx.ID_OK)])
    dialog.show(True)

@misc.handle
def poll_start(ui):
    try:
        while not stop_event.is_set():
            poll(ui)
    except Exception:
        log(traceback.format_exc())
        stop_event.set()
        wx.CallAfter(_show_error, ui, "GitHub Login Failed", "Could not contact GitHub. Check your connection and try again.")

@misc.handle
def start(loadingUi) -> bool:
    try:
        user = check_user_credentials()
    except Exception as e:
        loadingUi.Hide()
        stop_event.clear()
        ui = LoiginDialog(None, generate_code)
        thread = threading.Thread(target=poll_start, args=(ui,), daemon=True)
        thread.start()
        try:
            ui.show()
        finally:
            stop_event.set()
            thread.join(timeout=2)
        loadingUi.show()
        return success_event.is_set()
        
