import argparse
import sys

from . import __version__
from .errors import DepotError


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


def _register(sub):
    """Subcommands are attached here as tasks add them."""


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
