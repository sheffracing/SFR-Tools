import utils.platform.darwin as darwin
import subprocess
import time

import threading
from utils.git import Git, find_github_repo
from plugin import Plugin
from utils import build, settings
from pathlib import Path

git = Git()
#app = Plugin()

git.set_local_repo(find_github_repo("/Users/joseph/Documents/KiCad/SFR/Kicad/Boards/SFR18/example"))
#git.local_repo.git.checkout("main")
#git.fetch_latest_boards()
print(git.local_repo.git.diff("--", "Boards/SFR18/example/example.kicad_pcb"))

git.local_repo.git.checkout(
    "HEAD",
    "--",
    "Boards/SFR18/example/example.kicad_pcb"
)
print("\n\nDONE\n\n")
print(git.local_repo.git.diff("--", "Boards/SFR18/example/example.kicad_pcb"))


#git.pull_board(Path("/Users/joseph/Documents/KiCad/SFR/Kicad/Boards/SFR18/example"))

#git.checkout_branch("sfr18-example-onmort")
#git.stage_dir(Path("/Users/joseph/Documents/KiCad/SFR/Kicad/Boards"))
#git.commit_branch(Path("/Users/joseph/Documents/KiCad/SFR/Kicad/Boards/SFR18/example"), "sfr18-example-onmort")
#git.push_branch("sfr18-example-onmort")
