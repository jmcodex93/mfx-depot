"""Houdini preferences-directory discovery.

Port of houdini_pref_dirs() from MFX CamRig's installer/install.py --
the behavior is proven in production; keep it byte-compatible.
"""
import os
import platform
import re
from pathlib import Path

from .errors import DepotError

MIN_MAJOR = (21, 0)


def houdini_pref_dirs(extra=None):
    """Every Houdini >= MIN_MAJOR prefs dir on this machine, per platform,
    honoring HOUDINI_USER_PREF_DIR (with its __HVER__ token) when set."""
    found = []
    custom = os.environ.get("HOUDINI_USER_PREF_DIR")
    roots = []
    if custom:
        expanded = Path(custom.replace("__HVER__", "*"))
        roots.append((expanded.parent, expanded.name))
    system = platform.system()
    if system == "Darwin":
        roots.append((Path.home() / "Library/Preferences/houdini", "*"))
    elif system == "Windows":
        roots.append((Path.home() / "Documents", "houdini*"))
    else:
        roots.append((Path.home(), "houdini*"))
    for base, pat in roots:
        if not base.is_dir():
            continue
        for d in sorted(base.glob(pat)):
            m = re.search(r"(\d+)\.(\d+)$", d.name)
            if not m or not d.is_dir():
                continue
            if (int(m.group(1)), int(m.group(2))) >= MIN_MAJOR:
                found.append(d)
    if extra:
        p = Path(extra).expanduser()
        if not p.is_dir():
            raise DepotError("--prefs-dir %s does not exist" % p)
        found.append(p)
    seen, out = set(), []
    for d in found:
        r = d.resolve()
        if r not in seen:
            seen.add(r)
            out.append(d)
    if not out:
        raise DepotError(
            "no Houdini %d.%d+ preferences directory found.\n"
            "Searched the standard location for %s. Launch Houdini once so "
            "it creates its preferences, or pass --prefs-dir."
            % (MIN_MAJOR[0], MIN_MAJOR[1], platform.system()))
    return out


def pkg_dir(prefs):
    return prefs / "packages"
