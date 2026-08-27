"""Package inference: where is the payload root, what is it called,
which version is it. The manifest (mfx.json) refines; inference carries."""
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .errors import DepotError
from .registry import slugify

MARKER_DIRS = ("otls", "hda", "scripts", "toolbar", "vex", "ocl",
               "desktop", "presets", "gallery", "soho", "dso")
HDA_RE = re.compile(r"\.(hda|hdalc|hdanc|otl|otllc|otlnc)$", re.I)
NAME_VER_RE = re.compile(r"^(.*?)[\s_.-]*v?(\d+(?:\.\d+)*)$")
PY_LIBS_RE = re.compile(r"^python\d.*libs$")


@dataclass
class PackageInfo:
    name: str
    slug: str
    version: str
    root: Path
    env_var: str
    min_houdini: Optional[str] = None
    feed: Optional[str] = None
    shipped_pkg: Optional[Path] = None
    unversioned: bool = False


def _has_markers(d):
    for m in MARKER_DIRS:
        if (d / m).is_dir():
            return True
    pk = d / "packages"
    if pk.is_dir() and any(pk.glob("*.json")):
        return True
    for k in d.iterdir():
        if k.is_file() and HDA_RE.search(k.name):
            return True
        if k.is_dir() and PY_LIBS_RE.match(k.name):
            return True
    return False


def find_root(tree):
    d = Path(tree)
    while True:
        if _has_markers(d):
            return d
        kids = [k for k in d.iterdir()
                if k.is_dir() and not k.name.startswith((".", "__"))]
        files = [k for k in d.iterdir()
                 if k.is_file() and not k.name.startswith(".")]
        if len(kids) == 1 and not files:
            d = kids[0]
            continue
        return None


def clean_name(raw):
    s = re.sub(r"\(\d+\)", "", str(raw))
    s = re.sub(r"[\s_.-]*(final|latest|copy|master|main)[\s_.-]*$", "",
               s, flags=re.I)
    return s.strip(" _-.")


def split_name_version(stem):
    s = clean_name(stem)
    m = NAME_VER_RE.match(s)
    if m and m.group(1):
        return clean_name(m.group(1)), m.group(2)
    return s, None


def _load_manifest(root):
    p = root / "mfx.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise DepotError("%s is not valid JSON (%s).\nFix the manifest or "
                         "remove it to fall back to inference." % (p, e))
    if not isinstance(data, dict):
        raise DepotError("%s must contain a JSON object." % p)
    return data


def _find_shipped_pkg(root):
    pk = root / "packages"
    if pk.is_dir():
        hits = sorted(pk.glob("*.json"))
        if hits:
            return hits[0]
    for f in sorted(root.glob("*.json")):
        if f.name == "mfx.json":
            continue
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and ("env" in data or "path" in data
                                       or "hpath" in data):
            return f
    return None


def _hda_name_version(root):
    hdas = []
    for d in (root, root / "otls", root / "hda"):
        if d.is_dir():
            hdas += [f for f in sorted(d.iterdir())
                     if f.is_file() and HDA_RE.search(f.name)]
    for f in hdas:
        stem = HDA_RE.sub("", f.name)
        name, ver = split_name_version(stem)
        if ver:
            return name, ver
    if hdas:
        return HDA_RE.sub("", hdas[0].name), None
    return None, None


def inspect(root, name_hint=None, version_hint=None, override_name=None):
    root = Path(root)
    manifest = _load_manifest(root)
    shipped = _find_shipped_pkg(root)
    hda_name, hda_ver = _hda_name_version(root)

    name = (override_name or manifest.get("name")
            or (shipped.stem if shipped else None)
            or (clean_name(name_hint) if name_hint else None)
            or hda_name)
    if not name:
        raise DepotError("could not infer a package name for %s; "
                         "pass --name <name>" % root)
    version = (manifest.get("version") or version_hint or hda_ver)
    unversioned = not version
    if unversioned:
        version = "0.0+" + date.today().strftime("%Y%m%d")

    slug = slugify(name)
    return PackageInfo(
        name=str(name), slug=slug, version=str(version), root=root,
        env_var="MFX_" + slug.upper().replace("-", "_"),
        min_houdini=manifest.get("min_houdini"),
        feed=manifest.get("updates"),
        shipped_pkg=shipped, unversioned=unversioned)
