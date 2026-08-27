"""Depot updates itself through the same feed channel it manages."""
import os
import sys
from pathlib import Path

from . import __version__
from .errors import DepotError
from .feeds import fetch_feed, parse_version
from .sources import download
from .ui import confirm, out

DEFAULT_FEED = ("https://raw.githubusercontent.com/jmcodex93/mfx-depot/"
                "main/docs/updates/depot.json")


def self_update(assume_yes):
    self_path = Path(os.environ.get("MFX_SELF_PATH")
                     or sys.argv[0]).resolve()
    if self_path.suffix != ".pyz":
        raise DepotError(
            "self-update only replaces an installed mfx.pyz; this mfx runs "
            "from %s.\nUpdate your checkout with git instead." % self_path)
    feed_url = os.environ.get("MFX_DEPOT_FEED", DEFAULT_FEED)
    feed = fetch_feed(feed_url)
    latest = str(feed.get("latest") or "")
    if parse_version(latest) <= parse_version(__version__):
        out("mfx %s is up to date." % __version__)
        return 0
    out("mfx %s -> %s" % (__version__, latest))
    if feed.get("changelog"):
        out("  changelog: %s" % feed["changelog"])
    if not feed.get("url"):
        raise DepotError("the feed at %s gives no download URL." % feed_url)
    if not confirm("Proceed?", assume_yes):
        out("Nothing was changed.")
        return 0
    tmp = self_path.with_suffix(".pyz.new")
    download(feed["url"], tmp)
    os.replace(tmp, self_path)
    out("Done. mfx is now %s." % latest)
    return 0
