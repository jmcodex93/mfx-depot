"""Conflict and health scan. Read-only; every finding names a next step."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import DepotError
from .hda_index import operator_types
from .infer import HDA_RE
from .registry import loads_lax, mfx_root


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


def _prefs_scope(prefs):
    """Which Houdini loads this prefs dir: its version suffix ('21.0').
    A dir without one is its own scope -- only clashes with itself and
    with global owners."""
    m = re.search(r"(\d+)\.(\d+)$", Path(prefs).name)
    return m.group(0) if m else str(prefs)


def _loaded_together(who, scopes):
    """Owner groups a single Houdini actually loads at once. Global owners
    (scope None: ~/MFX payloads, registered in every prefs) join every
    group; per-prefs owners only meet others of the same version."""
    global_owners = {o for o in who if scopes.get(o) is None}
    versions = set()
    for o in who:
        if scopes.get(o) is not None:
            versions |= scopes[o]
    groups = []
    if not versions and len(global_owners) > 1:
        groups.append(global_owners)
    for v in sorted(versions):
        grp = global_owners | {o for o in who if scopes.get(o) is not None
                               and v in scopes[o]}
        if len(grp) > 1 and grp not in groups:
            groups.append(grp)
    return groups


def run(reg, prefs_dirs):
    findings = []
    owners = {}     # description -> scan root
    scopes = {}     # description -> None (global) | set of prefs versions

    for slug in sorted(reg["packages"]):
        e = reg["packages"][slug]
        root = mfx_root() / e["payload_dir"] / e["version"]
        if root.is_dir():
            owners["package '%s'" % slug] = root
            scopes["package '%s'" % slug] = None
        else:
            findings.append(("ERROR",
                "%s: payload %s missing on disk -> run 'mfx repair' for "
                "guidance" % (slug, root)))
    managed = {e["pkg_file"] for e in reg["packages"].values()}

    for prefs in prefs_dirs:
        scope = _prefs_scope(prefs)
        pdir = Path(prefs) / "packages"
        for f in sorted(pdir.glob("*.json")) if pdir.is_dir() else []:
            try:
                data = loads_lax(f.read_text())
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
                    if not isinstance(val, str):
                        continue
                    # Houdini path lists: ';'-separated, '&' = defaults
                    for tok in val.split(";"):
                        tok = tok.strip()
                        if not tok or tok == "&" or tok.startswith("$"):
                            continue
                        p = Path(tok)
                        if p.is_absolute() and not p.exists():
                            findings.append(("ERROR",
                                "%s points %s at %s, which does not exist "
                                "-> fix the path or delete the file"
                                % (f, var, tok)))
                        elif p.is_dir():
                            desc = "foreign package %s" % f.name
                            owners.setdefault(desc, p)
                            scopes.setdefault(desc, set()).add(scope)
        otls = Path(prefs) / "otls"
        if otls.is_dir():
            desc = "user otls (%s)" % prefs
            owners[desc] = otls
            scopes[desc] = {scope}

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
        for grp in _loaded_together(who, scopes):
            findings.append(("ERROR",
                "%s/%s is defined by %s -> keep one; Houdini silently "
                "loads whichever path comes last"
                % (table, op, " AND ".join(sorted(grp)))))

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
