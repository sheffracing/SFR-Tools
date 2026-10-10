from pathlib import Path
from dotenv import load_dotenv
import wx

from UX.settings import SettingsDialog
from utils import build, misc

env_path = Path(__file__).parents[1] / ".env"

load_dotenv(env_path)

@misc.handle
def get(menu):
    url = build.get("help_url")
    wx.LaunchDefaultBrowser(url)
