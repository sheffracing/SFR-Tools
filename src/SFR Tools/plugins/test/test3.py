import utils.platform.darwin as darwin
import subprocess
import time
from utils.git import Git, find_github_repo
from utils import settings, build
from pathlib import Path
import plugin
git = Git()
kicad = plugin.Plugin()

path = "Boards/SFR18/example"
path = Path("Boards") / "SFR18" / "example"

repo = find_github_repo(kicad.project.path)
git.set_local_repo(repo)

git.fetch_latest_boards()