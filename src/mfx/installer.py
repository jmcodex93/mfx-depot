"""Payload copy + package-json registration. One payload, N registrations.
All writes transactional: payload first, package files last, backups of
anything overwritten, restore on failure (spec section 5)."""
import json
import shutil
from pathlib import Path

from .errors import DepotError
from .feeds import parse_version
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
    src = info.root.resolve()
    dst = target.resolve()
    self_install = src == dst or dst in src.parents
    if not self_install:
        try:
            if target.exists():
                shutil.rmtree(target)   # reinstall same version = repair
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


def uninstall(slug, reg, prefs_dirs, purge):
    e = reg["packages"].get(slug)
    if not e:
        raise DepotError("%s is not installed. See 'mfx list'." % slug)
    removed = []
    dirs = {Path(p) for p in e.get("prefs") or []} | set(prefs_dirs)
    for prefs in sorted(dirs):
        f = Path(prefs) / "packages" / e["pkg_file"]
        if f.is_file():
            f.unlink()
            removed.append(str(f))
    if purge:
        pdir = mfx_root() / e["payload_dir"]
        if pdir.is_dir():
            shutil.rmtree(pdir)
    del reg["packages"][slug]
    return removed


def repair(reg, prefs_dirs, only_slug=None):
    report = []
    for slug in sorted(reg["packages"]):
        if only_slug and slug != only_slug:
            continue
        e = reg["packages"][slug]
        target = mfx_root() / e["payload_dir"] / e["version"]
        if not target.is_dir():
            report.append(
                "ERROR %s: payload %s missing on disk. Re-run "
                "'mfx install <original source>' to restore it."
                % (slug, target))
            continue
        data = e.get("pkg_data") or {
            "env": [{e["env_var"]: str(target)}], "path": "$" + e["env_var"]}
        register(e["pkg_file"], data, prefs_dirs)
        e["prefs"] = sorted({str(p) for p in prefs_dirs}
                            | set(e.get("prefs") or []))
        report.append("ok    %s: package files rewritten" % slug)
    return report


def rollback(slug, reg, prefs_dirs):
    e = reg["packages"].get(slug)
    if not e:
        raise DepotError("%s is not installed. See 'mfx list'." % slug)
    pdir = mfx_root() / e["payload_dir"]
    versions = sorted((d.name for d in pdir.glob("*") if d.is_dir()),
                      key=parse_version)
    if len(versions) < 2:
        raise DepotError(
            "rollback needs at least two installed versions in %s "
            "(found: %s). Install an older zip first."
            % (pdir, ", ".join(versions) or "none"))
    cur = e["version"]
    if cur not in versions or versions.index(cur) == 0:
        raise DepotError("%s is already at the oldest version (%s)."
                         % (slug, cur))
    prev = versions[versions.index(cur) - 1]
    target = pdir / prev
    data = (e.get("versions") or {}).get(prev) or {
        "env": [{e["env_var"]: str(target)}], "path": "$" + e["env_var"]}
    register(e["pkg_file"], data, prefs_dirs)
    e["version"] = prev
    e["pkg_data"] = data
    if e.get("pin"):
        e["pin"] = prev
    return cur, prev
