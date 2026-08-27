#!/usr/bin/env python3
"""MFX Depot bootstrap.

Run:  python3 get-depot.py [--yes] [--url URL]
Copies mfx.pyz (found next to this script, or downloaded from --url) into
~/MFX/depot/bin, writes 'mfx' shims, and prints the PATH line to add.
Standard library only, no telemetry. Re-running repairs.
"""
import argparse
import os
import shutil
import sys
import urllib.request
from pathlib import Path


def fail(msg):
    sys.stderr.write("\nERROR: %s\n" % msg)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--url", help="download mfx.pyz from this URL")
    args = ap.parse_args()

    bindir = Path(os.environ.get("MFX_ROOT")
                  or (Path.home() / "MFX")) / "depot" / "bin"
    print("MFX Depot bootstrap")
    print("  install to: %s" % bindir)
    if not args.yes:
        try:
            if input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Nothing was changed.")
                return
        except EOFError:
            fail("cannot ask for confirmation here; re-run with --yes")

    bindir.mkdir(parents=True, exist_ok=True)
    dest = bindir / "mfx.pyz"
    if args.url:
        try:
            req = urllib.request.Request(
                args.url, headers={"User-Agent": "mfx-depot"})
            with urllib.request.urlopen(req, timeout=10) as r, \
                    open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
        except OSError as e:
            fail("could not download %s (%s)" % (args.url, e))
    else:
        src = Path(__file__).resolve().parent / "mfx.pyz"
        if not src.is_file():
            fail("mfx.pyz not found next to this script.\nDownload the "
                 "release zip and run get-depot.py from inside it, or pass "
                 "--url <mfx.pyz url>.")
        shutil.copy2(src, dest)

    sh = bindir / "mfx"
    sh.write_text('#!/bin/sh\nexec python3 "%s" "$@"\n' % dest)
    sh.chmod(0o755)
    (bindir / "mfx.cmd").write_text('@python "%s" %%*\r\n' % dest)

    print("Done. Add this to your PATH (e.g. in ~/.zshrc):")
    print('  export PATH="%s:$PATH"' % bindir)
    print("Then open a new terminal and run: mfx list")


if __name__ == "__main__":
    main()
