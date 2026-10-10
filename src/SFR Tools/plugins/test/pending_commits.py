import utils.platform.darwin as darwin
import subprocess
import time
from utils.git import Git, find_github_repo
from utils import settings
from pathlib import Path
import plugin
git = Git()
kicad = plugin.Plugin()

path = "Boards/SFR18/example"
path = Path("Boards") / "SFR18" / "example"

repo = find_github_repo(kicad.project.path)
git.set_local_repo(repo)

branch = git.local_repo.active_branch.name

git.git(
            "fetch",
            "origin"
        )
commits = git.local_repo.git.log(
    "--branches",
    "--not",
    "--remotes=origin",
    "--oneline"
).strip()
print(commits)
print(bool(commits))
print(git.local_repo.active_branch.name)
print(git.local_repo.git.diff("--", "Boards/SFR18/example/example.kicad_pcb"))
if bool(commits):
    pass#git.push_branch(branch)