# SFR Tools

SFR Tools is a KiCad [IPC Plugin](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/index.html), it handles branch management, commits, fetching & pulling and Pull Requests with our private GitHub Repository.
> [!CAUTION]
> GitHub Desktop should **never** be used concurrently with SFR-Tools. Close the plugin before executing Git commands.

## Features
- **GitHub integration** — connect KiCad projects to a GitHub repository.
- **Autosaving** — While the plugin is open, it will automatically commit and push changes. 
- **Committing** — The plugin handles fetching, checkout, commits and pushes via a UI.
- **Pulling** — The plugin pulls any un-modified KiCad projects to the latest version on main and users can pull a board from a specific branch or commit at any time.
- **Pull requests** — Submit board changes for review on GitHub via PRs.
- **Review workflow** — keep design changes organised and traceable through pull requests.
- **Project restoration** — restore board folders from the main branch after their changes have been merged.
- **PCM distribution** — package and distribute the plugin through KiCad's Plugin and Content Manager.

## Installation
> [!TIP]
> Speak to your subteam lead if you are confused at any point.

### Prerequisites
1. Download GitHub Desktop [here](https://desktop.github.com/download/).
2. Install Git [here](https://git-scm.com/install/).
1. Install KiCad 10.0 [here](https://www.kicad.org/download/). Earlier versions are not supported.

### Plugin & Content Manager
> [!TIP]
> In future you can easily update all of your packages by clicking Update All

1. Open KiCad 10.0
2. Open the **Plugin and Content Manager**
3. Click *Manage* (top right of screen)
4. Click **+**
5. Enter the following link and click *OK*:
```
https://raw.githubusercontent.com/sheffracing/SFR-Tools/main/repository.json
```
6. Click *Save* and select `Sheffield Formula Racing` in the drop-down at the top
7. Search for **SFR Tools**.
8. Install the plugin and click *Apply Pending Changes* (bottom right)

### Manual Installation

If KiCad PCM auto-fetching is unavailable, manual installation is possible.

1. Download the appropriate packaged release from [GitHub Releases](https://github.com/sheffracing/SFR-Tools/releases)
2. Open the **Plugin and Content Manager**
3. Click *Install from file* and select the .zip file
4. Restart KiCad

## How It Works

SFR Tools uses Git to track changes to projects, and manages commits on a per-folder basis.
### Startup
> [!NOTE]
> If a User Access Token (UAT) cannot be found, the user is requested to login via the OAuth Device flow (GitHub App) and a UAT is generated before the plugin is launched

- A GitHub Installation Access Token (IAT) is fetched from [our API](https://github.com/sheffracing/SFR-Tools/tree/main/app#readme).
- A protobuf connection is established to the currently running KiCad instance.
- Git checks for any outstanding unresolved conflicts, and pulls any un-modified boards.
- Any pending changes are committed, and the repo is pushed. 
- The autosave worker thread is started.

### Saving (commit/push)
> [!CAUTION]
> The repo has a strict **one branch per-user** per-board. Conflicts are managed via PRs by subteam leads and **not** during project development.
> Subteam leads will be alerted if a user other than the branch author causes a conflict.

Stashing and branch checkouts aren't used. The aim is that the user doesn't have to manually check out and commit via GitHub Desktop. Stashing changes and then checking out the target branch **before** KiCad is opened would be the normal approach to preserve changes on other boards, however pending changes on other boards would have to be popped once the user exits their current KiCad instance, and stash/checkout would have to be executed before the user opens KiCad. 

This is impossible to detect, and so a temporary index is constructed. It inherits the HEAD of the target branch, then stages the board's changes and commits. The end result is exactly the same, the only difference is that the user remains checked out on main during the whole process.

- Create a temporary index and inherit the branch's HEAD
- Stage changes from the board's directory
- Give commit authorship to user and GitHub App
- Check if the commit can be squashed
  - Decided if the commit message is identical to the previous commit that came before it
- Construct a commit using the temp index
- Push to GitHub using the IAT

### Downloading (pull)
- The user selects a target board
- Optionally, the user can select:
  - Target branch HEAD (by default this is `main`)
  - Target commit (by default this is `main` HEAD)
- If the user is currently inside this board, pending changes are abandoned and KiCad exits.
- The user's branch and board directory is "restored" to the target source
- If the user had this board open before this operation, KiCad is re-opened.
- The plugin exits, and the user is urged to restart it.

### Project Review (PR)
> [!IMPORTANT]
> Due to a bug with the GitHub PR API, Review requests made for teams fail silently

- A description of changes is requested of the user
- Metadata of the current KiCad and plugin instance (version etc) is added
- PR is created by the GitHub App using the IAT
- User is made an assignee
- "PCB Review" label and "Order Deadline" milestone is added
- Review request for the "Electrical Lead" team is made

## Development

### Repository Structure

```text
SFR-Tools/
├── .github/
│   └── workflows/
├── scripts/
├── src/
│   └── SFR-Tools/
│       ├── metadata.json
│       ├── plugins/
│       └── resources/
├── README.md
└── ...
```

### Getting Started

1. Clone the repository:

   ```bash
   git clone https://github.com/sheffracing/SFR-Tools.git
   cd SFR-Tools
   ```
2. Uninstall the plugin via PCM if you already have it installed.
2. Open the project in [VS Code](https://code.visualstudio.com/download).
3. make a symlink between `src/SFR-Tools/plugins` and `/${KICAD_VERSION}/3rdparty/plugins/com_github_sheffracing_sfr-tools`
4. Make changes on a dev branch.


### Releases

SFR Tools uses GitHub Releases and a GitHub Actions workflow to prepare and distribute plugin versions.
The workflow updates the `metadata.json` version number, packages it and releases it on GitHub. `repository.json` and `packages.json` are updated with the new version. Refrain from manually updating these files as changes may be overwritten by a future release.

Tag your commit with the following format to start the workflow:

```text
sfr-tools/vX.Y.Z
```

Replace `X.Y.Z` with the intended release version.
For more information, see [RELEASE.md](https://github.com/sheffracing/SFR-Tools/blob/main/RELEASE.md)

## License

See the repository's `LICENSE` file for licensing terms.

---

<p align="center">
  <sub>Sheffield Formula Racing</sub>
</p>
