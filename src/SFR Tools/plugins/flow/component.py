from pathlib import Path

import wx
from dotenv import load_dotenv

from UX.component import Component
from UX.info import InfoDialog
from utils.log import log
from utils import misc

env_path = Path(__file__).parents[1] / ".env"

load_dotenv(env_path)

@misc.handle
def get(menu):
    ui = Component(menu)
    response = ui.show()
    if response == wx.ID_YES:
        ui = InfoDialog(menu, "Success", "Symbols and Footprints uploaded to the Shared Library", "Success", [("Close", wx.ID_CLOSE)])
        ui.show()
