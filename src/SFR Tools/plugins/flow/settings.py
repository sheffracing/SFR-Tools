from pathlib import Path
from dotenv import load_dotenv

from UX.settings import SettingsDialog
from utils import misc

env_path = Path(__file__).parents[1] / ".env"

load_dotenv(env_path)

@misc.handle
def get(menu):
    ui = SettingsDialog(menu)
    ui.show(True)
