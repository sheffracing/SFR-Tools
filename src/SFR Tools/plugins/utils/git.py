import requests

try:   
    from utils.log import log
    from github import Github, Auth
    from github.GithubException import BadCredentialsException, UnknownObjectException

    from git import Repo, Actor, Commit, exc
    from git import Git as PyGit
    from git.exc import InvalidGitRepositoryError, NoSuchPathError
    from utils import settings, build, misc
    from urllib.parse import urlparse
    import os
    from dotenv import load_dotenv, set_key
    from pathlib import Path
    import requests
    from datetime import datetime
    import json
    import time
    import traceback
    import base64
    import tempfile

except Exception as e:
    log(traceback.format_exc(),True)
env_path = Path(__file__).parents[1] / ".env"

class ExceptionCode(Exception):
    def __init__(self, code: int = 500, message: str = "Unknown Exception"):
        super().__init__(message)
        self.code = code

class NoChanges(Exception):
    def __init__(self):
        super().__init__("No changes detected")

class Conflicting(Exception):
    def __init__(self):
        super().__init__("Conflicting changes between origin/main and local")

load_dotenv(env_path)

def check_user_credentials():
    user_auth = Auth.Token(os.environ.get("ACCESS_TOKEN"))
    user = Github(auth=user_auth)
    try:
        return user.get_user().login
    except BadCredentialsException:
        raise ExceptionCode(401,"Bad credentials (user)")   

def find_github_repo(path: Path = "."):
    path = str(path)
    owner, repo_name = build.get("github/repo").split("/", 1)
    try:
        git_repo = Repo(path, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as e:
        return None

    for remote in git_repo.remotes:
        for url in remote.urls:
            url = url.strip()

            if url.startswith("https://github.com/"):
                path_part = urlparse(url).path
            elif url.startswith("git@github.com:"):
                path_part = url.split(":", 1)[1]
            else:
                continue

            path_part = path_part.strip("/")
            if path_part.endswith(".git"):
                path_part = path_part[:-4]

            parts = path_part.split("/")
            if len(parts) == 2:
                remote_owner, remote_repo = parts
                if remote_owner == owner and remote_repo == repo_name:
                    return git_repo

    return None


# Auto renew IAT if it has expired.
def request(func = None):
    def wrapper(self, *args,**kwargs):
        if not self.token or self.token_expires.timestamp() <= datetime.now().timestamp():
            try:
                self.get_token()
                self.github = Github(auth=Auth.Token(self.token))
                self.repo = self.github.get_repo(build.get("github/repo"))
            except BaseException as e:
                raise ExceptionCode(500,"Unknown Error fetching remote token")
        return func(self, *args,**kwargs) if func else None
    return wrapper

# Verify the class object has a local repo loaded. 
def repo(func = None):
    def wrapper(self, *args,**kwargs):
        if not self.local_repo:
            raise ExceptionCode(404, "Local repository not found")
        return func(self, *args,**kwargs) if func else None
    return wrapper


# Notes:
# This is the only permitted interface with the plugin that is allowed to be used. 
# IATs have an expiry of 1h and the auth must be refreshed.
# Methods or classes which have an ancestor of a PyGithub created object must NEVER be returned to the caller.
# There's no good way to keep track of all objects created, thus auth cannot be refreshed across all of them.
# You can return identifiers such as sha hashes or ids instead, for future calls to fetch associated objects from this.
# GitPython objects are safe to return, but no Git functions requiring auth should ever be ran outside of this package.

# To ensure an IAT doesn't need refreshing, use the @request decorator

#Manage a Github App installation on behalf of a user.  
class Git():   
    def __init__(self):
        self.user_auth = Auth.Token(os.environ.get("ACCESS_TOKEN"))
        self.user = Github(auth=self.user_auth)
        try:
            username = self.user.get_user().login
            settings.set("github/login", username)
        except BadCredentialsException:
            raise ExceptionCode(401,"Bad credentials (when init server)")   

        self.token = os.environ.get("INSTALLATION_TOKEN")

        expires = os.environ.get("INSTALLATION_EXPIRES")
        if expires:
            self.token_expires: datetime = datetime.fromtimestamp(float(expires)) 
        else:
            self.token_expires: datetime = datetime.now()

        request()(self) #Request new token (if required)

        if not self.token:
            raise ExceptionCode(401)
        self.github = Github(auth=Auth.Token(self.token))
        self.repo = self.github.get_repo(build.get("github/repo"))
        self.local_repo: Repo = None
        self.local_root: Path = None

    def get_token(self) -> bool:
        response = requests.get(build.get("github/token_url"), headers={"Authorization": self.user_auth.token})
        if response.status_code == 429 and "retry-after" in response.headers:
            time.sleep(int(response.headers["retry-after"]))
            return self.get_token()
        elif response.status_code == 429:
            raise ExceptionCode(500, "Server is Rate-limited but did not provide limit")
        if not response.status_code == 200:
            data = response.json()
            if not "detail"  in data:
                raise ExceptionCode(response.status_code, "Unknown Error (detail unavailable)")
            else:
                raise ExceptionCode(response.status_code, data["detail"])
        data = response.json()
        if not "access_token" in data or not "expires" in data:
            raise ExceptionCode(500, "Server did not provide credentials")
        self.token = data["access_token"]
        self.token_expires = datetime.fromisoformat(data["expires"].replace("Z", "+00:00"))
        set_key(env_path, key_to_set="INSTALLATION_TOKEN", value_to_set=self.token)
        set_key(env_path, key_to_set="INSTALLATION_EXPIRES", value_to_set=str(self.token_expires.timestamp()))
        return True
    
    @request
    def clone(self, path: Path):
        url = f"https://github.com/{build.get()}/{build.get('github/repo')}.git"
        pass

    # Wrapper for authenticated Git requests.
    @request
    @repo
    def git(self, *args):
        credentials = base64.b64encode(
            f"x-access-token:{self.token}".encode()
        ).decode()
        return self.local_repo.git.execute([
            "git",
            "-c",
            f"http.extraHeader=Authorization: Basic {credentials}",
            *args
        ])

    # Get an Actor object of the authenticated user.
    @request
    def get_actor(self):
        user = self.user.get_user()
        return Actor(
            user.name or user.login,
            user.email or f"{user.login}@users.noreply.github.com"
        )
    
    # Get public info on the App. Must be used for fetching it's "user id" for attributing commits.
    def get_bot_user_info(self) -> json:
        response = requests.get(f"https://api.github.com/users/{build.get('github/slug')}[bot]")
        if response.status_code == 200:
            return response.json()
        
    # Get all active branch names under the remote repo.
    @request
    def get_branches(self) -> list[str]:
        return [branch.name.removeprefix("origin/") for branch in list(self.repo.get_branches())]
    
    @request
    @repo
    # Get all commit ids (sha hash) associated with the given branch on the remote repo.
    def get_branch_commits(self, branch: str = "main") -> list[Commit]:
        return list(self.local_repo.iter_commits(f"origin/main..origin/{branch}"))

    @request
    # Get all cars seen on the remote repo, given the branch.
    def get_cars(self, branch: str = "main") -> list[str]:
        try:
            content = self.repo.get_contents(f"{build.get('github/car_path')}", ref=branch)
            return [item.name for item in list(content) if item.type == "dir" and item.name.find(build.get("car/prefix"),0) == 0]
        except UnknownObjectException as e:
            log(traceback.format_exc(),True)
            return []
    
    @request
    # Get all board names seen on the repo remote associated with the current car, given the branch.
    def get_boards(self, branch: str = "main") -> list[str]:
        car = settings.get("info/car")
        if not car or car not in build.get("car/cars"):
            car = build.get("car/cars")[0]
            settings.set("info/car", car)
        try:
            content = self.repo.get_contents(f"{build.get('github/car_path')}/{car}", ref=branch)
            return [item.name for item in list(content) if item.type == "dir"]# and self.get_board_metadata(item.name, branch) != None]
        except UnknownObjectException as e:
            log("no boards")
            return []
    def get_full_commit_sha(self, id: str):
        commit = self.repo.get_commit(id)
        if commit and commit.sha:
            return commit.sha

    # Set the local repo, used by Git.
    def set_local_repo(self, repo: Repo):
        self.local_repo = repo
        self.local_root = Path(repo.working_tree_dir)

        #with repo.config_writer() as config:
        #    config.set_value("gpg", "format", "ssh")
        #    config.set_value("user", "signingkey", str(Path(__file__).parents[1] / "keys" / "sign.pub"))
        #    config.set_value("commit", "gpgsign", "false")

    # Checkout local branch with Git.
    @misc.handle
    @repo
    def checkout_branch(self,branch: str, project_path: Path = None):
        local_exists = branch in [head.name for head in self.local_repo.heads]
        remote_exists = branch in self.get_branches()

        if (local_exists and remote_exists) or local_exists:
            log("A")
            try:
                self.local_repo.git.checkout(branch)
            except exc.GitCommandError as e:
                if "would be overwritten by checkout" not in (e.stderr or ""):
                    raise
                self.stash_and_apply(branch, project_path)
            self.local_repo.git.reset()
        elif remote_exists:
            log("B")
            self.local_repo.git.checkout("-b", branch, f"origin/{branch}")
            self.local_repo.git.reset()
        else:
            log("C")
            self.local_repo.git.checkout("-b", branch, "origin/main")

    #Stash pending uncommited changes, checkout branch and re-commit.
    @misc.handle
    @repo
    def stash_and_apply(self, branch: str, project_path: Path):
        log("stashing and applying")
        self.local_repo.git.stash("push", "-u", "-m", "SFR Tools startup changes")
        self.local_repo.git.checkout(branch)
        try:
            self.local_repo.git.stash("pop")
        except exc.GitCommandError:
            # Stashed/user version wins
            self.local_repo.git.checkout("--theirs", "--", str(project_path))

            # Mark the conflicts resolved
            self.local_repo.git.add("--", str(project_path))

    # Stage changes within a specifed directory.
    @repo
    def stage_dir(self, path: Path):
        relative = path.absolute().relative_to(self.local_root)
        self.local_repo.git.add("--", str(relative))

    # Commit staged files to a specified branch
    @request
    @repo
    def commit_branch_v0(self, project_path: Path, branch: str, message: str = None, description: str = None):
        self.git(
            "fetch",
            "origin"
        )

        self.checkout_branch(branch, project_path)
        if self.local_repo.active_branch.name == "main":
            raise Exception("Checkout failed, Aborting commit")

        self.stage_dir(project_path)

        changes = self.local_repo.index.diff("HEAD")

        if len(changes) == 0:
            raise NoChanges()

        if not message:
            message = f"Autosaved {str(project_path.name or 'Board')} via SFR Tools"
        if description:
            message += f"\n\n{description}"

        author = self.get_actor()
        bot_info = self.get_bot_user_info()
        if "id" in bot_info:
            bot = Actor(
                f"{build.get('github/slug')}[bot]",
                f"{bot_info['id']}+{build.get('github/slug')}[bot]@users.noreply.github.com"
            )
        else:
            bot = author

        if self.local_repo.head.commit.message.strip().splitlines()[0] == message.strip().splitlines()[0]:
            # GitPython does not have a good API for amendments. Use the legacy git object and set env vars for bot attribution
            env = os.environ.copy()
            env["GIT_COMMITTER_NAME"] = bot.name
            env["GIT_COMMITTER_EMAIL"] = bot.email
            return self.local_repo.git.commit(
                "--amend", "-m", 
                f"{message}\nThis commit was squashed to a previous commit.",
                author = f"{author.name} <{author.email}>",
                env = env
            )
        
        return self.local_repo.index.commit(message=message, author=author, committer=bot)

    # Push any pending commits to a specified branch on the remote repo
    @request
    @repo
    def push_branch(self, branch: str = "main"):
        self.git(
            "push",
            "origin",
            branch,
            "--set-upstream",
            "--force-with-lease"
        )
        self.checkout_branch("main")

    # Executes pull_board() but additionally commits so that a remote branch mirrors local. Wipes any and all data within the board's folder on the local repo. USE WITH CAUTION.
    @request
    @repo
    def restore_board(self, remote_path: Path, branch: str = "main", source: str = "origin/main"):
        self.pull_board(remote_path, source)
        self.git(
            "fetch",
            "origin"
        )
        try:
            self.commit_branch(
                project_path = self.local_root / remote_path, 
                branch = branch,
                message = f"Restore to {source}",
                description=f"This branch was restored to another branch HEAD or a previous commit using the Pull Flow.\nThis action was performed automatically by SFR Tools." 
            )
            #self.push_branch(branch)
        finally:
            pass

    # Pull a specified board from a branch. Wipes any and all data within the board's folder on the local repo. USE WITH CAUTION.
    @request
    @repo
    def pull_board(self, remote_path: Path, source: str = "origin/main"):
        self.git(
            "fetch",
            "origin",
        )

        self.local_repo.git.restore(
            f"--source={source}",
            "--staged",
            "--worktree",
            "--",
            str(remote_path)
        )
#
        #self.local_repo.git.clean(
        #    "-fd",
        #    "--",
        #    str(remote_path)
        #)

    @request
    def __get_existing_pr(self, branch: str = "main"):
        prs = self.repo.get_pulls(
            state="open",
            head=f"{build.get('github/org')}:{branch}",
            base="main"
        )
        return prs[0] if prs.totalCount else None
    
    # Check if a PR already exists, specified with the branch.
    def pr_exists(self, branch: str = "main"):
        return bool(self.__get_existing_pr(branch))

    # Check if a branch exists on the remote repo.
    @request
    @repo
    def remote_branch_exists(self, branch: str = "main") -> bool:
        self.git(
            "fetch",
            "origin",
            "--prune"
        )

        return any(
            ref.remote_head == branch
            for ref in self.local_repo.remotes.origin.refs
        )
    def get_pr_url(self, branch: str = "main"):
        pr = self.__get_existing_pr(branch)
        if pr:
            return pr.html_url
        
    # Create a PR.
    @request
    def make_pr(self, project_path: Path, branch: str = "main", description: str = "No Response", kicad_version: str = "Unknown", review: bool = True):
        user = self.user.get_user()
        milestone = self.repo.get_milestone(build.get("github/milestones/order"))
        pr = self.__get_existing_pr(branch)
        if not pr:
            pr = self.repo.create_pull(
                title=f"Review {project_path.name} PCB",
                body=f"""
**Board:** {project_path.name}
**Author:** {user.name or user.login}
**KiCad Version:** {kicad_version}
**SFR Tools Version:** {build.get("version")}
<details open>
<summary>Description</summary>
{description}
</details>


This action was performed automatically by SFR Tools.
""",
                head=branch,
                base="main",
                draft=False,
                maintainer_can_modify=True,
            )
        pr.add_to_assignees(user.login)
        pr.add_to_labels(build.get("github/labels/pcb"))
        
        if not review:
            return pr.html_url
        pr.create_review_request(
            team_reviewers=[build.get("github/teams/reviewer")]
        )
        pr.add_to_labels(build.get("github/labels/review"))
        issue = self.repo.get_issue(pr.number)
        issue.edit(milestone=milestone)
        return pr.html_url

    def find_branches_for_directory(self, project_path: Path) -> list[str]:
        project_path = str(project_path).rstrip("/")
        matches: list[str] = []

        for branch in self.local_repo.branches:
            if branch.name == "main":
                continue

            changed_files: list[str] = self.local_repo.git.diff("--name-only", f"origin/main...{branch.name}").splitlines()

            if any(path == project_path or path.startswith(project_path + "/")for path in changed_files):
                matches.append(branch.name)
        return matches
    def find_directory_for_branch(self, branch: str) -> Path:
        changed_files: list[str] = self.local_repo.git.diff(
            "--name-only",
            f"origin/main...{branch}"
        ).splitlines()

        directories: set[Path] = set()

        for file in changed_files:
            path = Path(file)

            try:
                boards_index = path.parts.index("Boards")
            except ValueError:
                continue

            if len(path.parts) <= boards_index + 1:
                continue

            directory = Path(*path.parts[:boards_index + 2])
            directories.add(directory)
    
        if len(directories) != 1:
            raise ValueError(
                f"Expected exactly one directory under Boards for branch "
                f"{branch!r}, found: {sorted(map(str, directories))}"
            )
    
        return directories.pop()

    # Delete dormant branches and local branches which are not present on the remote repo. DO NOT call this before the first autosave call.
    def prune_deleted_branches(self):
        self.git(
            "fetch",
            "origin",
            "--prune"
        )
        for branch in self.local_repo.branches:
            if not self.remote_branch_exists(str(branch)):
                self.local_repo.delete_head(branch, force=True)

    def main_changed_board(self, project_path: Path, branch: str = "main", ):
        merge_base = self.local_repo.git.merge_base(
            branch,
            "origin/main"
        ).strip()

        diff = self.local_repo.git.diff(
            "--name-only",
            merge_base,
            "origin/main",
            "--",
            str(project_path)
        )

        return bool(diff.strip())

    # Prune branches and fetch any boards from main which do not have changes
    @repo
    def fetch_latest_boards(self):
        self.prune_deleted_branches()
        boards = self.local_root / build.get("github/car_path") / settings.get("info/car")
        for path in boards.iterdir():
            if not path.is_dir():
                continue
            if not self.dir_exists_remotely(path):
                continue
                
            relative = path.relative_to(self.local_root)
            modified_branches = self.find_branches_for_directory(relative)

            if len(modified_branches) == 0:
                self.pull_board(relative)
                continue
            elif self.is_conflicting(modified_branches[0]):
                raise Conflicting()
                log("branch conflicting")

    # Check if any commits on the local repo are not yet pushed
    @request
    @repo
    def outstanding_commits(self) -> bool:
        self.git(
            "fetch",
            "origin"
        )
        return bool(
        self.local_repo.git.log(
            "--branches",
            "--not",
            "--remotes=origin",
            "--oneline"
        ).strip()
    )

    # Check if a board on the local repo conflicts with remote. Do not run this when a commit is pending a push.
    @request
    @repo
    def is_conflicting(self, branch: str = "main"):
        self.git(
            "fetch",
            "origin"
        )

        local_commit = self.local_repo.commit(f"{branch}").hexsha
        remote_commit = self.local_repo.commit(f"origin/{branch}").hexsha

        return local_commit != remote_commit

    # Check if a folder exists on the remote repo
    @request
    @repo
    def dir_exists_remotely(self, project_path: str, source: str = "origin/main"):
        self.git(
            "fetch",
            "origin"
        )
        return bool(
            self.local_repo.git.ls_tree(
                "-d",
                source,
                "--",
                str(project_path)
            ).strip()
        )
    
    @request
    def upload_ssh_key(self):
        pass
        key = (Path(__file__). parents[1] / "keys" / "sign.pub").read_text()
        print(f"Key: {key}")
        response = requests.post(
            "https://api.github.com/user/ssh_signing_keys",
            headers = {
                "Authorization": f"Bearer {self.user_auth.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10"
            },
            json = {
                "key": key,
                "title": "SFR Tools (Signing)"
            }
        )
        if response.status_code != 201:
            raise ExceptionCode(response.status_code, response.json()["message"])
    @request
    def get_uploaded_ssh_keys(self):
        response = requests.get(
            "https://api.github.com/user/ssh_signing_keys",
            headers = {
                "Authorization": f"Bearer {self.user_auth.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10"
            }
        )
        if response.status_code != 200:
            raise ExceptionCode(response.status_code, response.json()["message"])
        data = response.json()
        for key_data in data:
            print(key_data)

    @repo
    @request
    def commit_branch(self, project_path: Path, branch: str, message: str = None, description: str = None):
        project_path = Path(project_path).resolve()

        # Work only with paths inside this repository.
        try:
            relative = project_path.relative_to(self.local_root).as_posix()
        except ValueError:
            raise ValueError("Project path is outside the repository")

        if not project_path.is_dir():
            raise FileNotFoundError(project_path)

        # Do not update the branch currently checked out.
        if not self.local_repo.head.is_detached and self.local_repo.active_branch.name == branch:
            raise RuntimeError(
                f"{branch} is currently checked out. "
                "Keep the main working tree on another branch."
            )

        self.git("fetch", "origin")

        # Get HEAD on last commit from branch (used to construct temp index)
        local_exists = branch in [b.name for b in self.local_repo.branches]
        remote_ref = f"refs/remotes/origin/{branch}"
        remote_exists = remote_ref in [r.path for r in self.local_repo.refs]

        if local_exists:
            parent = self.local_repo.commit(branch)
        elif remote_exists:
            parent = self.local_repo.commit(remote_ref)
        else:
            parent = self.local_repo.commit("origin/main")

        parent_sha = parent.hexsha

        # Commit details
        message = message or "Autosave"
        if description:
            message += f"\n\n{description}"

        author = self.get_actor()
        bot_info = self.get_bot_user_info()

        if "id" in bot_info:
            bot = Actor(
                f"{build.get('github/slug')}[bot]",
                f"{bot_info['id']}+{build.get('github/slug')}[bot]@users.noreply.github.com"
            )
        else:
            bot = author

        # Create an independent index, based on the target branch.
        fd, index_file = tempfile.mkstemp(prefix="sfr-index-")
        os.close(fd)
        os.unlink(index_file)

        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = index_file

        env["GIT_AUTHOR_NAME"] = author.name
        env["GIT_AUTHOR_EMAIL"] = author.email
        env["GIT_COMMITTER_NAME"] = bot.name
        env["GIT_COMMITTER_EMAIL"] = bot.email

        try:
            # Create temp index from parent commit
            self.local_repo.git.execute(
                ["git", "read-tree", parent_sha],
                env=env,
            )

            # Stage directory
            self.local_repo.git.execute(
                ["git", "add", "-A", "--", relative],
                env=env,
            )

            # Create tree
            tree = self.local_repo.git.execute(
                ["git", "write-tree"],
                env=env,
            ).strip()

            old_tree = self.local_repo.git.execute(
                ["git", "rev-parse", f"{parent_sha}^{{tree}}"]
            ).strip()

            if tree == old_tree:
                raise NoChanges()

            # Determine whether to squash the previous commit
            subject = parent.message.strip().splitlines()[0]
            squash = subject == message.strip().splitlines()[0]

            if squash:
                message += "\nThis commit was squashed to a previous commit."
                parents = [p.hexsha for p in parent.parents]
            else:
                parents = [parent_sha]

            # Create commit without checking out the target branch
            args = ["git", "commit-tree", tree]

            for p in parents:
                args.extend(["-p", p])

            args.extend(["-m", message])

            commit_sha = self.local_repo.git.execute(
                args,
                env=env,
            ).strip()

            # Determine whether the previous commit is on the remote branch
            remote_ref = f"refs/remotes/origin/{branch}"
            remote_exists = remote_ref in [
                ref.path for ref in self.local_repo.refs
            ]

            pushed = False

            if remote_exists:
                remote_commit = self.local_repo.commit(remote_ref)

                pushed = parent_sha in {
                    commit.hexsha
                    for commit in self.local_repo.iter_commits(remote_ref)
                }

            # Push the new commit using authenticated Git operations
            if squash and pushed:
                # Only amend safely if the remote still points to the commit
                # being replaced.
                if remote_commit.hexsha != parent_sha:
                    raise RuntimeError(
                        "Cannot squash commit: remote branch has advanced "
                        "beyond the commit being replaced."
                    )

                self.git(
                    "push",
                    f"--force-with-lease=refs/heads/{branch}:{parent_sha}",
                    "origin",
                    f"{commit_sha}:refs/heads/{branch}",
                )
            else:
                self.git(
                    "push",
                    "origin",
                    f"{commit_sha}:refs/heads/{branch}",
                )

            # Update an existing local branch reference without checking it out
            if local_exists:
                self.local_repo.git.update_ref(
                    f"refs/heads/{branch}",
                    commit_sha,
                    parent_sha,
                )

            return commit_sha

        finally:
            if os.path.exists(index_file):
                os.unlink(index_file)