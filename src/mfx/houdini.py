"""Find installed Houdinis and their hython (python port of CamRig's
bin/_hfs.sh resolution)."""
import glob
import os
import platform
import re
from pathlib import Path

from .errors import DepotError


def find_houdinis():
    system = platform.system()
    if system == "Darwin":
        pats = ["/Applications/Houdini/Houdini*"]
    elif system == "Windows":
        pats = [r"C:\Program Files\Side Effects Software\Houdini*"]
    else:
        pats = ["/opt/hfs*"]
    hits = []
    for pat in pats:
        hits += [p for p in glob.glob(pat) if re.search(r"\d", p)]

    def key(p):
        return tuple(int(x) for x in re.findall(r"\d+", Path(p).name))
    return sorted(hits, key=key)


def hython_path(hfs):
    hfs = Path(hfs)
    system = platform.system()
    if system == "Darwin":
        m = re.search(r"(\d+\.\d+)", hfs.name)
        ver = m.group(1) if m else ""
        p = (hfs / "Frameworks/Houdini.framework/Versions" / ver
             / "Resources/bin/hython")
    elif system == "Windows":
        p = hfs / "bin" / "hython.exe"
    else:
        p = hfs / "bin" / "hython"
    if not p.is_file():
        raise DepotError(
            "hython not found at %s.\nPass --hfs pointing at a Houdini "
            "install dir (the Houdini<version> folder)." % p)
    return p


def pick_hython(hfs_flag=None):
    override = os.environ.get("MFX_HYTHON")
    if override:
        return Path(override)
    if hfs_flag:
        return hython_path(hfs_flag)
    houdinis = find_houdinis()
    if not houdinis:
        raise DepotError(
            "no Houdini installation found on this machine.\n"
            "Install Houdini 21.0+ or pass --hfs <houdini install dir>.")
    return hython_path(houdinis[-1])
