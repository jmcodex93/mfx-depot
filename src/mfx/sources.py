"""Acquire an install source into a local tree. Local kinds here;
URL/GitHub kinds are added by the network milestone (M2)."""
import shutil
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


def _acquire_url(url, workdir):
    raise DepotError("URL sources are not implemented yet.")
