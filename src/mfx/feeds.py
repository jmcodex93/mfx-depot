"""Opt-in update checks: static JSON feeds + GitHub releases.
Never called except from 'mfx update' / 'mfx self-update'."""
import json
import re
import urllib.error
import urllib.request

from .errors import DepotError
from .sources import GITHUB_URL_RE, TIMEOUT, UA, github_archive


def parse_version(s):
    nums = re.findall(r"\d+", str(s or ""))
    return tuple(int(x) for x in nums) or (0,)


def fetch_feed(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise DepotError("could not read the update feed %s (%s)."
                         % (url, e))


def check(entry):
    """One package's update status; soft-fails with {'error': ...}."""
    current = entry.get("version")
    feed_url = entry.get("feed")
    if feed_url:
        try:
            feed = fetch_feed(feed_url)
        except DepotError as e:
            return {"error": str(e)}
        latest = str(feed.get("latest") or "")
        return {"current": current, "latest": latest,
                "url": feed.get("url") or "",
                "changelog": feed.get("changelog") or "",
                "min_houdini": feed.get("min_houdini"),
                "newer": parse_version(latest) > parse_version(current)}
    ref = str((entry.get("source") or {}).get("ref") or "")
    gh = GITHUB_URL_RE.match(ref)
    if gh:
        try:
            url, latest = github_archive(gh.group(1), gh.group(2))
        except DepotError as e:
            return {"error": str(e)}
        return {"current": current, "latest": latest or "",
                "url": ref, "changelog": "", "min_houdini": None,
                "newer": parse_version(latest) > parse_version(current)}
    return None
