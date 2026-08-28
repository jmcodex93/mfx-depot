"""Static package catalog: curated JSON in the public repo.
Read-only; network only when the user runs search/install-by-name."""
import json
import os
import urllib.error
import urllib.request

from .errors import DepotError
from .registry import cache_dir
from .sources import TIMEOUT, UA

DEFAULT_CATALOG_URL = ("https://raw.githubusercontent.com/jmcodex93/"
                       "mfx-depot/main/catalog.json")


def catalog_url():
    return os.environ.get("MFX_CATALOG_URL", DEFAULT_CATALOG_URL)


def cache_path():
    return cache_dir() / "catalog.json"


def _parse(raw, origin):
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise DepotError("the catalog at %s is not valid JSON (%s).\n"
                         "Report it or retry later." % (origin, e))
    if not isinstance(data, dict) or not isinstance(data.get("packages"), list):
        raise DepotError("the catalog at %s has an unexpected format." % origin)
    return data


def fetch():
    """Return (catalog_data, from_cache). Network failure falls back to
    the cached copy; a malformed download never does."""
    url = catalog_url()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as e:
        cp = cache_path()
        if cp.is_file():
            return _parse(cp.read_text(), str(cp)), True
        raise DepotError(
            "could not fetch the catalog from %s (%s) and no cached copy "
            "exists.\nCheck your connection and re-run." % (url, e))
    data = _parse(raw, url)
    cache_dir().mkdir(parents=True, exist_ok=True)
    tmp = cache_path().with_suffix(".tmp")
    tmp.write_text(raw)
    os.replace(tmp, cache_path())
    return data, False


def _entries(data):
    return [e for e in data.get("packages", [])
            if isinstance(e, dict) and e.get("slug")]


def find(data, term=None):
    hits = []
    for e in _entries(data):
        if term is None:
            hits.append(e)
            continue
        hay = " ".join([str(e.get("slug", "")), str(e.get("name", "")),
                        str(e.get("description", ""))]
                       + [str(t) for t in (e.get("tags") or [])]).lower()
        if term.lower() in hay:
            hits.append(e)
    return hits


def resolve(data, name):
    entries = _entries(data)
    for e in entries:
        if e["slug"] == name:
            return e
    lname = str(name).lower()
    hits = [e for e in entries if str(e.get("name", "")).lower() == lname]
    return hits[0] if len(hits) == 1 else None
