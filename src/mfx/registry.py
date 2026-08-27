"""Depot state: ~/MFX layout, installed.json, adoption of legacy installs."""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .errors import DepotError

SCHEMA = 1


def mfx_root():
    return Path(os.environ.get("MFX_ROOT") or (Path.home() / "MFX"))


def depot_dir():
    return mfx_root() / "depot"


def backups_dir():
    return depot_dir() / "backups"


def cache_dir():
    return depot_dir() / "cache"


def state_path():
    return depot_dir() / "installed.json"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name):
    """Lowercase-dashed slug. The MFX brand prefix is stripped so a fresh
    'MFX CamRig' zip and a legacy MFX_CAMRIG adoption land on the SAME
    slug ('camrig') -- one package, one entry."""
    s = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    if s.startswith("mfx-") and len(s) > len("mfx-"):
        s = s[len("mfx-"):]
    if not s:
        raise DepotError("cannot derive a package name from %r; "
                         "pass --name <name>" % name)
    return s


def loads_lax(text):
    """json.loads with Houdini's package-file tolerances: // comments and
    trailing commas (real MOPS_Plus.json / Modeler.json load fine in
    Houdini). Raises json.JSONDecodeError if still invalid."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        else:
            out.append(c)
        i += 1
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))


def load():
    p = state_path()
    if not p.is_file():
        return {"schema": SCHEMA, "packages": {}}
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise DepotError(
            "%s is unreadable (%s).\nIt can be re-derived from disk: move "
            "the file aside and run 'mfx repair'." % (p, e))
    if data.get("schema") != SCHEMA:
        raise DepotError(
            "%s has schema %r; this mfx understands schema %d.\n"
            "Run 'mfx self-update' to get a newer mfx."
            % (p, data.get("schema"), SCHEMA))
    data.setdefault("packages", {})
    return data


def save(data):
    depot_dir().mkdir(parents=True, exist_ok=True)
    tmp = state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, state_path())


def new_entry(**kw):
    e = {"name": None, "slug": None, "version": None, "payload_dir": None,
         "env_var": None, "pkg_file": None, "pkg_data": None, "versions": {},
         "source": {"kind": None, "ref": None}, "installed_at": now(),
         "pin": None, "feed": None, "min_houdini": None, "prefs": []}
    e.update(kw)
    return e


def adopt(data, prefs_dirs):
    """Import packages installed by the per-product install.py scripts
    (env var MFX_*, payload under mfx_root). Never moves files."""
    adopted = []
    root = mfx_root().resolve()
    for prefs in prefs_dirs:
        pdir = prefs / "packages"
        if not pdir.is_dir():
            continue
        for f in sorted(pdir.glob("*.json")):
            try:
                pkg = loads_lax(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue        # doctor reports broken files; adoption skips
            env = pkg.get("env")
            if not isinstance(env, list):
                continue
            for item in env:
                if not isinstance(item, dict):
                    continue
                for var, val in item.items():
                    if not (isinstance(var, str) and var.startswith("MFX_")
                            and isinstance(val, str)):
                        continue
                    target = Path(val)
                    try:
                        target.resolve().relative_to(root)
                    except ValueError:
                        continue
                    slug = var[len("MFX_"):].lower().replace("_", "-")
                    e = data["packages"].setdefault(slug, new_entry(
                        name=f.stem, slug=slug, version=target.name,
                        payload_dir=target.parent.name, env_var=var,
                        pkg_file=f.name,
                        source={"kind": "adopted", "ref": str(f)}))
                    if str(prefs) not in e["prefs"]:
                        e["prefs"].append(str(prefs))
                    if slug not in adopted and e["source"]["kind"] == "adopted":
                        adopted.append(slug)
    return adopted
