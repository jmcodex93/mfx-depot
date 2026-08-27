"""Scene lockfile: which packages/versions does a hip actually use."""
import json
import os
import pkgutil
import subprocess
import tempfile
from pathlib import Path

from .errors import DepotError
from .houdini import pick_hython
from .registry import mfx_root


def run_helper(hython, hip):
    src = pkgutil.get_data("mfx", "hython_helpers/lock_scene.py")
    fd, helper = tempfile.mkstemp(suffix=".py", prefix="mfx_lock_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(src)
        r = subprocess.run([str(hython), helper, str(hip)],
                           capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(helper)
    if r.returncode != 0 or not r.stdout.strip():
        raise DepotError(
            "hython could not analyze %s:\n%s\nIf the scene needs a newer "
            "Houdini, pass --hfs." % (hip, (r.stderr or "").strip()[-2000:]))
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except ValueError as e:
        raise DepotError("unexpected hython output for %s (%s)" % (hip, e))


def map_records(payload, reg, scene):
    pkgs, embedded, unresolved, seen = {}, [], [], set()
    root = mfx_root()
    for rec in payload.get("records", []):
        key = (rec["type"], rec["library"])
        if key in seen:
            continue
        seen.add(key)
        lib = rec["library"]
        if lib == "Embedded":
            embedded.append(rec["type"])
            continue
        owner = None
        for slug in sorted(reg["packages"]):
            e = reg["packages"][slug]
            vroot = str(root / e["payload_dir"] / e["version"])
            if lib.startswith(vroot + os.sep) or lib.startswith(vroot + "/"):
                owner = (slug, e)
                break
        if owner:
            slug, e = owner
            p = pkgs.setdefault(slug, {"name": e["name"], "slug": slug,
                                       "version": e["version"], "types": []})
            p["types"].append(rec["type"])
        else:
            unresolved.append({"type": rec["type"], "library": lib})
    return {"schema": 1, "houdini": payload.get("houdini"),
            "scene": str(scene),
            "packages": [pkgs[s] for s in sorted(pkgs)],
            "embedded": sorted(set(embedded)),
            "unresolved": unresolved}


def lock(hip, reg, hfs_flag=None):
    hip = Path(hip)
    if not hip.is_file():
        raise DepotError("%s does not exist." % hip)
    hython = pick_hython(hfs_flag)
    payload = run_helper(hython, hip)
    return map_records(payload, reg, hip.name)
