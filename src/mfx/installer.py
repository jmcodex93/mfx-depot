"""Payload copy + package-json registration. One payload, N registrations.
All writes transactional: payload first, package files last, backups of
anything overwritten, restore on failure (spec section 5)."""
import json
import shutil
from pathlib import Path

from .errors import DepotError
from .registry import backups_dir, mfx_root, new_entry, now


def default_pkg_file(slug):
    return "MFX_%s.json" % slug.replace("-", "_")


def payload_target(info, reg):
    entry = reg["packages"].get(info.slug)
    payload_dir = entry["payload_dir"] if entry else info.slug
    return mfx_root() / payload_dir / info.version


def render_pkg_json(info, target):
    if info.shipped_pkg:
        try:
            data = json.loads(info.shipped_pkg.read_text())
        except (json.JSONDecodeError, OSError) as e:
            raise DepotError("%s (the package json shipped inside the "
                             "package) is unreadable: %s" % (info.shipped_pkg, e))
        return _rewrite(data, info.root.resolve(), target)
    data = {"env": [{info.env_var: str(target)}], "path": "$" + info.env_var}
    if info.min_houdini:
        data["enable"] = "houdini_version >= '%s'" % info.min_houdini
    return data


def _rewrite(node, src_root, target):
    if isinstance(node, dict):
        return {k: _rewrite(v, src_root, target) for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite(v, src_root, target) for v in node]
    if isinstance(node, str):
        return _rewrite_str(node, src_root, target)
    return node


def _rewrite_str(s, src_root, target):
    if s.startswith("$"):
        return s                          # tokens pass through
    p = Path(s)
    if p.is_absolute():
        try:
            return str(target / p.resolve().relative_to(src_root))
        except (ValueError, OSError):
            pass
        # creator's stale absolute path from their machine: repoint at root
        if not p.exists():
            return str(target)
        return s
    rel = s[2:] if s.startswith("./") else s
    if (src_root / rel).exists():
        return str(target / rel)
    return s


def register(pkg_file_name, data, prefs_dirs):
    stamp_dir = backups_dir() / now().replace(":", "-")
    done = []       # (written_path, backup_path_or_None, existed_before)
    text = json.dumps(data, indent=2) + "\n"
    try:
        for prefs in prefs_dirs:
            pdir = Path(prefs) / "packages"
            pdir.mkdir(parents=True, exist_ok=True)
            dest = pdir / pkg_file_name
            bak = None
            if dest.exists():
                stamp_dir.mkdir(parents=True, exist_ok=True)
                bak = stamp_dir / ("%s__%s__%s" % (
                    Path(prefs).parent.name, Path(prefs).name, pkg_file_name))
                shutil.copy2(dest, bak)
            dest.write_text(text)
            done.append((dest, bak))
    except (OSError, PermissionError) as e:
        for dest, bak in done:
            try:
                if bak:
                    shutil.copy2(bak, dest)
                else:
                    dest.unlink()
            except OSError:
                pass
        raise DepotError(
            "could not write a package file under %s (%s).\nAlready-written "
            "prefs dirs were rolled back; nothing changed. Fix the folder's "
            "permissions and re-run." % (prefs, e))


def apply(info, reg, prefs_dirs, source):
    """Install payload + register everywhere + update registry entry."""
    entry = reg["packages"].get(info.slug)
    pkg_file = (entry or {}).get("pkg_file") or default_pkg_file(info.slug)
    payload_dir = (entry or {}).get("payload_dir") or info.slug
    target = mfx_root() / payload_dir / info.version
    try:
        if target.exists():
            shutil.rmtree(target)       # reinstall same version = repair
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(info.root, target)
    except (OSError, PermissionError) as e:
        raise DepotError("could not copy the payload to %s (%s).\n"
                         "Check disk space and permissions." % (target, e))
    data = render_pkg_json(info, target)
    register(pkg_file, data, prefs_dirs)
    e = entry or new_entry()
    versions = e.get("versions") or {}
    versions[info.version] = data
    e.update(name=info.name, slug=info.slug, version=info.version,
             payload_dir=payload_dir, env_var=info.env_var,
             pkg_file=pkg_file, pkg_data=data, versions=versions,
             source=source, installed_at=now(),
             feed=info.feed or e.get("feed"),
             min_houdini=info.min_houdini or e.get("min_houdini"),
             prefs=sorted({str(p) for p in prefs_dirs}
                          | set(e.get("prefs") or [])))
    reg["packages"][info.slug] = e
    return target
