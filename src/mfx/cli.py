import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import __version__, infer, installer, registry, sources, feeds
from . import prefs as prefs_mod
from .errors import DepotError
from .selfupdate import self_update
from .ui import confirm, out


def build_parser():
    ap = argparse.ArgumentParser(
        prog="mfx",
        description="MFX Depot - install and lifecycle manager for Houdini "
                    "packages and HDAs.")
    ap.add_argument("--version", action="version",
                    version="mfx %s" % __version__)
    ap.set_defaults(func=None)
    sub = ap.add_subparsers(dest="command", metavar="command")
    _register(sub)
    return ap


def load_state(prefs_dirs):
    """Registry + one-time adoption of legacy install.py installs."""
    reg = registry.load()
    if registry.adopt(reg, prefs_dirs):
        registry.save(reg)
    return reg


def install_source(source, override_name, prefs_dirs, reg, assume_yes):
    """Shared by 'mfx install' and 'mfx update' (Task 10)."""
    with tempfile.TemporaryDirectory(prefix="mfx_") as td:
        tree, hints = sources.acquire(source, Path(td))
        root = infer.find_root(tree)
        if root is None:
            raise DepotError(
                "no Houdini package found in %s.\nExpected otls/, hda/, "
                "scripts/, toolbar/ or .hda files somewhere inside. If this "
                "really is a package, install its payload folder directly."
                % source)
        info = infer.inspect(root, name_hint=hints.get("name"),
                             version_hint=hints.get("version"),
                             override_name=override_name)
        prev = reg["packages"].get(info.slug)
        out("%s %s" % (info.name, info.version))
        if info.unversioned:
            out("  (no version found in the source; using a dated fallback)")
        if prev:
            out("  replaces: %s %s (from %s)"
                % (prev["name"], prev["version"], prev["source"]["ref"]))
            out("  To keep both, re-run with --name <other-name>.")
        out("  install to : %s" % installer.payload_target(info, reg))
        pkg_file = ((prev or {}).get("pkg_file")
                    or installer.default_pkg_file(info.slug))
        for p in prefs_dirs:
            out("  register in: %s" % (prefs_mod.pkg_dir(p) / pkg_file))
        if not confirm("Proceed?", assume_yes):
            out("Nothing was changed.")
            return 0
        installer.apply(info, reg, prefs_dirs,
                        {"kind": "url" if "://" in str(source) else "local",
                         "ref": str(source)})
        registry.save(reg)
        out("Done. Restart Houdini to load %s." % info.name)
        return 0


def cmd_install(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs(args.prefs_dir)
    reg = load_state(prefs_dirs)
    return install_source(args.source, args.name, prefs_dirs, reg, args.yes)


def cmd_list(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs()
    reg = load_state(prefs_dirs)
    if not reg["packages"]:
        out("No packages installed. Try: mfx install <zip|folder|url>")
    for slug in sorted(reg["packages"]):
        e = reg["packages"][slug]
        flags = []
        if e.get("pin"):
            flags.append("pinned %s" % e["pin"])
        if e["source"]["kind"] == "adopted":
            flags.append("(adopted)")
        if str(e.get("version", "")).startswith("0.0+"):
            flags.append("(unversioned)")
        out("%-24s %-12s %s" % (slug, e["version"], " ".join(flags)))
    if args.all:
        managed = {e["pkg_file"] for e in reg["packages"].values()}
        for p in prefs_dirs:
            for f in sorted(prefs_mod.pkg_dir(p).glob("*.json")):
                if f.name not in managed:
                    out("%-24s %-12s foreign: %s" % (f.stem, "-", f))
    return 0


def cmd_info(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs()
    reg = load_state(prefs_dirs)
    e = reg["packages"].get(args.name) or reg["packages"].get(
        registry.slugify(args.name))
    if not e:
        raise DepotError("%s is not installed. See 'mfx list'." % args.name)
    show = {k: e[k] for k in ("name", "slug", "version", "payload_dir",
                              "env_var", "pkg_file", "source", "installed_at",
                              "pin", "feed", "min_houdini", "prefs")}
    out(json.dumps(show, indent=2, sort_keys=True))
    return 0


def cmd_uninstall(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs()
    reg = load_state(prefs_dirs)
    slug = args.name if args.name in reg["packages"] else registry.slugify(args.name)
    e = reg["packages"].get(slug)
    if not e:
        raise DepotError("%s is not installed. See 'mfx list'." % args.name)
    out("Uninstall %s %s" % (e["name"], e["version"]))
    dirs = {Path(p) for p in e.get("prefs") or []} | set(prefs_dirs)
    for prefs in sorted(dirs):
        f = Path(prefs) / "packages" / e["pkg_file"]
        if f.is_file():
            out("  will remove: %s" % f)
    if args.purge:
        out("  will DELETE %s (all versions)"
            % (registry.mfx_root() / e["payload_dir"]))
    if not confirm("Proceed?", args.yes):
        out("Nothing was changed.")
        return 0
    installer.uninstall(slug, reg, prefs_dirs, args.purge)
    registry.save(reg)
    out("Uninstalled." + ("" if args.purge else
        "  Files kept in %s (use --purge to delete)."
        % (registry.mfx_root() / e["payload_dir"])))
    return 0


def cmd_repair(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs()
    reg = load_state(prefs_dirs)
    only_slug = None
    if args.name:
        only_slug = args.name if args.name in reg["packages"] else registry.slugify(args.name)
        if only_slug not in reg["packages"]:
            raise DepotError("%s is not installed. See 'mfx list'." % args.name)
    num_pkgs = 1 if only_slug else len(reg["packages"])
    num_prefs = len(prefs_dirs)
    out("Repair will rewrite package files for %d package(s) in %d prefs dir(s)" % (num_pkgs, num_prefs))
    if not confirm("Proceed?", args.yes):
        out("Nothing was changed.")
        return 0
    report = installer.repair(reg, prefs_dirs, only_slug=only_slug)
    registry.save(reg)
    errors = 0
    for line in report:
        out(line)
        errors += line.startswith("ERROR")
    if not report:
        out("Nothing to repair.")
    return 1 if errors else 0


def cmd_update(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs()
    reg = load_state(prefs_dirs)
    slugs = [args.name] if args.name else sorted(reg["packages"])
    if args.name and args.name not in reg["packages"]:
        raise DepotError("%s is not installed. See 'mfx list'." % args.name)
    rc = 0
    for slug in slugs:
        e = reg["packages"][slug]
        status = feeds.check(e)
        if status is None:
            out("%-24s no update channel (no feed, not from GitHub)" % slug)
            continue
        if "error" in status:
            out("%-24s check failed: %s" % (slug, status["error"]))
            continue
        if not status["newer"]:
            out("%-24s up to date (%s)" % (slug, e["version"]))
            continue
        if e.get("pin"):
            out("%-24s %s -> %s available, but pinned at %s (mfx unpin %s)"
                % (slug, e["version"], status["latest"], e["pin"], slug))
            continue
        out("%-24s %s -> %s" % (slug, e["version"], status["latest"]))
        if status["changelog"]:
            out("  changelog: %s" % status["changelog"])
        if not status["url"]:
            out("  the feed gives no download URL; get the new version "
                "from the creator and 'mfx install' it.")
            continue
        rc = install_source(status["url"], e["name"], prefs_dirs, reg,
                            args.yes) or rc
    return rc


def cmd_pin(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs()
    reg = load_state(prefs_dirs)
    e = reg["packages"].get(args.name)
    if not e:
        raise DepotError("%s is not installed. See 'mfx list'." % args.name)
    if args.pin_version and args.pin_version != e["version"]:
        raise DepotError(
            "%s is at %s, not %s. Pin freezes the CURRENT version; use "
            "'mfx rollback %s' first to change versions."
            % (args.name, e["version"], args.pin_version, args.name))
    e["pin"] = e["version"]
    registry.save(reg)
    out("%s pinned at %s (excluded from 'mfx update')."
        % (args.name, e["pin"]))
    return 0


def cmd_unpin(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs()
    reg = load_state(prefs_dirs)
    e = reg["packages"].get(args.name)
    if not e:
        raise DepotError("%s is not installed. See 'mfx list'." % args.name)
    e["pin"] = None
    registry.save(reg)
    out("%s unpinned." % args.name)
    return 0


def cmd_rollback(args):
    prefs_dirs = prefs_mod.houdini_pref_dirs()
    reg = load_state(prefs_dirs)
    e = reg["packages"].get(args.name)
    if not e:
        raise DepotError("%s is not installed. See 'mfx list'." % args.name)
    out("Rolling back %s from %s" % (e["name"], e["version"]))
    if not confirm("Proceed?", args.yes):
        out("Nothing was changed.")
        return 0
    cur, prev = installer.rollback(args.name, reg, prefs_dirs)
    registry.save(reg)
    out("Done: %s -> %s. Restart Houdini." % (cur, prev))
    return 0


def cmd_self_update(args):
    return self_update(args.yes)


def _register(sub):
    p = sub.add_parser("install", help="install a package from a zip, "
                       "folder, .hda file or URL")
    p.add_argument("source")
    p.add_argument("--name", help="override the inferred package name")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--prefs-dir", help="also register in this prefs dir")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("list", help="list installed packages")
    p.add_argument("--all", action="store_true",
                   help="also show package files not managed by mfx")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("info", help="show one package's registry entry")
    p.add_argument("name")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("uninstall", help="unregister a package")
    p.add_argument("name")
    p.add_argument("--purge", action="store_true",
                   help="also delete the installed files")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("repair", help="rewrite package files from the registry")
    p.add_argument("name", nargs="?")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_repair)

    p = sub.add_parser("update", help="check feeds and apply updates (opt-in)")
    p.add_argument("name", nargs="?")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("pin", help="freeze a package at its current version")
    p.add_argument("name")
    p.add_argument("pin_version", nargs="?")
    p.set_defaults(func=cmd_pin)

    p = sub.add_parser("unpin", help="allow updates again")
    p.add_argument("name")
    p.set_defaults(func=cmd_unpin)

    p = sub.add_parser("rollback", help="switch back to the previous version")
    p.add_argument("name")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_rollback)

    p = sub.add_parser("self-update", help="update mfx itself")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_self_update)


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.func is None:
        ap.print_help(sys.stderr)
        return 1
    try:
        return args.func(args) or 0
    except DepotError as e:
        sys.stderr.write("\nERROR: %s\n" % e)
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted; nothing may be half-written - "
                         "run 'mfx repair' if in doubt.\n")
        return 1
