# MFX Depot — Package manager for Houdini

**mfx** is a local package manager for Houdini packages and HDAs. Install, update, and manage packages from zips, folders, URLs, or GitHub in a single command — replacing hand-editing of `packages/*.json`. Supports Houdini 21.0+, macOS/Windows/Linux, Python 3.9+ stdlib only.

## Installation

Download the latest release zip from [GitHub](https://github.com/jmcodex93/mfx-depot/releases) (once published), unzip it, and run the bootstrap script:

```bash
unzip mfx-depot-0.2.0.zip
cd mfx-depot
python3 get-depot.py
```

This creates `~/MFX/depot/bin/mfx` and `mfx.cmd` (Windows), prints the PATH line to add to your shell profile, and prompts you to add it to your terminal profile.

For non-interactive use (scripts), add `--yes`:

```bash
python3 get-depot.py --yes
```

Alternative: if you have only the URL to `mfx.pyz`, download it directly:

```bash
python3 get-depot.py --url https://github.com/jmcodex93/mfx-depot/releases/download/v0.2.0/mfx.pyz --yes
```

## Usage

```
mfx install <source> [--name N] [--yes] [--prefs-dir DIR]
mfx list [--all]
mfx info <name>
mfx update [name] [--yes]
mfx pin <name> [version]     mfx unpin <name>
mfx rollback <name>
mfx uninstall <name> [--purge] [--yes]
mfx repair [name]
mfx doctor
mfx lock <scene.hip> [-o out.json] [--hfs DIR]
mfx self-update
```

- `install`: Package source can be a local zip, folder, bare `.hda` file, GitHub URL (repo/release/archive), or direct zip URL. The command auto-detects the package name and version, or you can override with `--name`.
- `list`: Shows all installed packages with versions, pins, and flags. `--all` additionally lists foreign package files (read-only).
- `update`: Check feeds for new versions. Opt-in only — never runs on a timer. Prints current → latest with changelog and asks for confirmation.
- `pin` / `unpin`: Freeze a package at its current version (excluded from `update`).
- `rollback`: Switch back to the previous installed version.
- `uninstall`: Remove package files. `--purge` also deletes payloads from `~/MFX/<Package>/`.
- `repair`: Rewrite package `.json` files and report missing payloads.
- `doctor`: Scan for HDA type conflicts, toolbar menu collisions, and broken packages.
- `lock`: Export which packages and versions a Houdini scene uses — reproducible for sharing scenes.
- `self-update`: Update mfx itself via its own feed.

## Package manifest

Optional `mfx.json` at your package root (all fields optional):

```json
{
  "name": "MFX CamRig",
  "version": "2.0",
  "min_houdini": "21.0",
  "updates": "https://raw.githubusercontent.com/.../camrig.json"
}
```

## Update feed format

Packages can declare an `updates` feed URL that responds with JSON:

```json
{"latest": "2.1", "url": "https://…", "changelog": "…", "min_houdini": "21.0"}
```

All fields optional. For GitHub-sourced packages, `mfx update` auto-checks releases if no feed is declared.

## Constraints

- **Stdlib only:** No external Python dependencies. Works offline; network access only on explicit `install` from URL, `update`, or `self-update`.
- **No telemetry:** Depot never collects usage data.
- **Opt-in updates:** Packages must be pinned to exclude them from `update`. Pinned packages never auto-update.

## Development

- `bin/test`: Run the fast test suite (no Houdini required). 135 tests covering install, update, repair, doctor, lockfile, and edge cases.
- `bin/qa`: Pre-release QA on real Houdini 21.0 and 22.0 installs (requires `--hfs` or auto-discovery). Tests package loading, lockfile accuracy, and tier-2 integration.
- `bin/build`: Build `dist/mfx.pyz` (zipapp) and platform shims for distribution.
- `bin/release "changelog"`: Gated release: qa + build + gh release + feed.
- `bin/verify-catalog`: Install-check every free catalog entry.

## State location

All packages and metadata live under `~/MFX/` (override with `$MFX_ROOT`):

```
~/MFX/
  <Package>/<version>/…             package payloads
  depot/
    installed.json                  registry of what's installed
    backups/                         pre-install backups of foreign files
    cache/                           downloaded packages (safe to delete)
    bin/mfx.pyz  mfx  mfx.cmd       the tool + PATH shims
```
