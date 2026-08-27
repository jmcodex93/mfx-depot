"""Conflict and health scan. Read-only; every finding names a next step."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import DepotError
from .hda_index import operator_types
from .infer import HDA_RE
from .registry import mfx_root


def _hda_files(root):
    return [f for f in sorted(Path(root).rglob("*"))
            if f.is_file() and HDA_RE.search(f.name)]


def _shelf_tools(root):
    """[(tool_name, submenu, shelf_file, error_or_None)]"""
    out = []
    for f in sorted(Path(root).rglob("toolbar/*.shelf")):
        try:
            tree = ET.parse(f)
        except ET.ParseError as e:
            out.append((None, None, f, str(e)))
            continue
        for t in tree.getroot().iter("tool"):
            out.append((t.get("name"),
                        t.findtext("toolSubmenu") or "", f, None))
    return out


def run(reg, prefs_dirs):
    findings = []
    owners = {}     # description -> scan root

    for slug in sorted(reg["packages"]):
        e = reg["packages"][slug]
        root = mfx_root() / e["payload_dir"] / e["version"]
        if root.is_dir():
            owners["package '%s'" % slug] = root
        else:
            findings.append(("ERROR",
                "%s: payload %s missing on disk -> run 'mfx repair' for "
                "guidance" % (slug, root)))
    managed = {e["pkg_file"] for e in reg["packages"].values()}

    for prefs in prefs_dirs:
        pdir = Path(prefs) / "packages"
        for f in sorted(pdir.glob("*.json")) if pdir.is_dir() else []:
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError) as e:
                findings.append(("ERROR",
                    "broken package file %s (%s) -> fix the JSON or delete "
                    "the file" % (f, e)))
                continue
            if f.name in managed:
                continue
            for item in (data.get("env") or []):
                if not isinstance(item, dict):
                    continue
                for var, val in item.items():
                    if not isinstance(val, str) or val.startswith("$"):
                        continue
                    p = Path(val)
                    if p.is_absolute() and not p.exists():
                        findings.append(("ERROR",
                            "%s points %s at %s, which does not exist -> "
                            "fix the path or delete the file" % (f, var, val)))
                    elif p.is_dir():
                        owners.setdefault("foreign package %s" % f.name, p)
        otls = Path(prefs) / "otls"
        if otls.is_dir():
            owners["user otls (%s)" % prefs] = otls

    types = {}
    for owner, root in owners.items():
        for f in _hda_files(root):
            try:
                for table, op in operator_types(f):
                    types.setdefault((table, op), set()).add(owner)
            except DepotError:
                findings.append(("WARN",
                    "could not read the operator index of %s (skipped)" % f))
    for (table, op), who in sorted(types.items()):
        if len(who) > 1:
            findings.append(("ERROR",
                "%s/%s is defined by %s -> keep one; Houdini silently "
                "loads whichever path comes last"
                % (table, op, " AND ".join(sorted(who)))))

    tools = {}
    for owner, root in owners.items():
        for name, sub, f, err in _shelf_tools(root):
            if err:
                findings.append(("WARN", "unparseable shelf %s (%s)" % (f, err)))
            elif name:
                tools.setdefault(name, set()).add(owner)
    for name, who in sorted(tools.items()):
        if len(who) > 1:
            findings.append(("WARN",
                "TAB tool '%s' is provided by %s -> expect duplicate TAB "
                "menu entries" % (name, " AND ".join(sorted(who)))))
    return findings
