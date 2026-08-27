"""Acquire an install source into a local tree. Local kinds here;
URL/GitHub kinds are added by the network milestone (M2)."""
import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from .errors import DepotError
from .infer import HDA_RE, split_name_version


def acquire(source, workdir):
    """Return (tree, hints). tree is a directory to run inference on;
    hints may carry 'name'/'version' gleaned from the source itself."""
    if "://" in str(source):
        return _acquire_url(str(source), Path(workdir))   # Task 9
    p = Path(source).expanduser()
    if p.is_dir():
        return p, {"name": p.name}
    if p.is_file() and HDA_RE.search(p.name):
        name, ver = split_name_version(HDA_RE.sub("", p.name))
        tree = Path(workdir) / "hda_pkg"
        (tree / "otls").mkdir(parents=True)
        shutil.copy2(p, tree / "otls" / p.name)
        hints = {"name": name}
        if ver:
            hints["version"] = ver
        return tree, hints
    if p.is_file() and p.suffix.lower() == ".zip":
        tree = Path(workdir) / "unzipped"
        tree.mkdir(parents=True)
        extract_zip(p, tree)
        # zip filenames give a usable NAME but their version digits are
        # untrustworthy ("MyTool_v2" vs the hda's real 1.5) -- the spec's
        # version chain (section 6) deliberately excludes them.
        name, _ = split_name_version(p.stem)
        return tree, {"name": name}
    if p.exists():
        raise DepotError("don't know how to install %s "
                         "(expected a folder, a .zip or an .hda file)." % p)
    raise DepotError("%s does not exist." % p)


def extract_zip(zpath, dest):
    try:
        with zipfile.ZipFile(zpath) as z:
            for m in z.namelist():
                mp = Path(m)
                if mp.is_absolute() or ".." in mp.parts:
                    raise DepotError(
                        "%s contains an unsafe path (%s); refusing to "
                        "extract. Get a clean copy of the package." % (zpath, m))
            z.extractall(dest)
    except zipfile.BadZipFile:
        raise DepotError("%s is not a valid zip file." % zpath)


TIMEOUT = 10
UA = {"User-Agent": "mfx-depot"}
GITHUB_URL_RE = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$")


def download(url, dest):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r, \
                open(dest, "wb") as f:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
    except (urllib.error.URLError, OSError) as e:
        raise DepotError(
            "could not download %s (%s).\nCheck the URL and your "
            "connection, then re-run." % (url, e))
    return dest


def _api_json(path):
    base = os.environ.get("MFX_GITHUB_API", "https://api.github.com")
    req = urllib.request.Request(base + path, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def github_archive(owner, repo):
    """Best downloadable archive: release asset > release zipball >
    first tag zipball > default-branch archive. Returns (url, version)."""
    try:
        rel = _api_json("/repos/%s/%s/releases/latest" % (owner, repo))
        version = (rel.get("tag_name") or "").lstrip("v") or None
        for a in rel.get("assets") or []:
            if str(a.get("name", "")).lower().endswith(".zip"):
                return a["browser_download_url"], version
        if rel.get("zipball_url"):
            return rel["zipball_url"], version
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        pass
    try:
        tags = _api_json("/repos/%s/%s/tags" % (owner, repo))
        if tags:
            return (tags[0]["zipball_url"],
                    str(tags[0].get("name", "")).lstrip("v") or None)
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        pass
    try:
        meta = _api_json("/repos/%s/%s" % (owner, repo))
        branch = meta.get("default_branch") or "main"
        web = os.environ.get("MFX_GITHUB_WEB", "https://github.com")
        return ("%s/%s/%s/archive/refs/heads/%s.zip"
                % (web, owner, repo, branch)), None
    except (urllib.error.URLError, OSError, ValueError):
        raise DepotError(
            "could not reach GitHub for %s/%s.\nCheck the repository name "
            "and your connection; private repos are not supported yet."
            % (owner, repo))


def _acquire_url(url, workdir):
    hints = {}
    gh = GITHUB_URL_RE.match(url)
    if gh and not url.lower().endswith(".zip"):
        owner, repo = gh.group(1), gh.group(2)
        url, version = github_archive(owner, repo)
        hints["name"] = repo
        if version:
            hints["version"] = version
    zpath = workdir / "download.zip"
    download(url, zpath)
    tree = workdir / "unzipped"
    tree.mkdir(parents=True)
    extract_zip(zpath, tree)
    if "name" not in hints:
        # Decode URL-encoded path before extracting stem
        path = urllib.parse.unquote(url.split("?")[0])
        stem = Path(path).stem
        name, _ = split_name_version(stem)   # name only; see local zip note
        hints["name"] = name
    return tree, hints
