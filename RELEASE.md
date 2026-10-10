# SFR-Tools KiCad PCM releases

A Github Action workflow automatically handles releases and publishing to SFR's PCM Repo, allowing team members to auto-update packages from KiCad without the need for Git.

The workflow manages `repository.json` and `packages.json`, alongside version numbers inside `metadata.json`. Modifications of these files may be overwritten upon release.

## What the workflow does

- Packages only the selected `src/<package>/` directory.
- Updates the package source `metadata.json` to the tagged version.
- Creates a ZIP with the package contents at the ZIP root.
- Uploads that ZIP to a GitHub Release matching the tag.
- Adds the release to `packages.json` without deleting older versions.
- Recalculates `repository.json`'s `packages.json` hash and timestamp.
- Commits the updated source metadata and index files to the default branch.

The workflow uses the built-in `GITHUB_TOKEN`; The org has granted it read & write repo access.

## Tag convention
Create and push a package-specific tag:
```bash
git tag sfr-tools/v1.2.0
git push origin sfr-tools/v1.2.0
```
The tag slug is matched to a folder in `src/` by converting its name to lowercase hyphenated text. For example, `sfr-tools` matches `src/SFR-Tools/metadata.json`.

The version must be numeric (`1.2.0`, not `1.2.0-alpha`) because KiCad PCM package versions use numeric components. Use GitHub Release titles or notes for prerelease labels.

The release tag **MUST** point to `main`. The workflow packages the exact tagged source and then pushes metadata updates to the default branch. If `main` has advanced after the tag was created, the final push may be rejected.

## Hosting

Add this URL to KiCad's Plugin and Content Manager:

`https://raw.githubusercontent.com/sheffracing/SFR-Tools/main/repository.json`
