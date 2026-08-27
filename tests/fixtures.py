"""Programmatic fixtures: realistic package shapes from the wild."""
import json
import zipfile
from pathlib import Path

SHELF_XML = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="%(tool)s" label="%(label)s" icon="MISC_generic">
    <toolMenuContext name="viewer">
      <contextNetType>SOP</contextNetType>
    </toolMenuContext>
    <toolSubmenu>%(submenu)s</toolSubmenu>
    <script scriptType="python"><![CDATA[pass]]></script>
  </tool>
</shelfDocument>
"""


def make_dummy_hda(path, table="Sop", optype="mfx::dummy::1.0",
                   label="Dummy"):
    """A text stand-in whose index blocks match what hda_index.py scans for."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "INDX\nOperator:  %s\nLabel:     %s\nPath:      oplib:/%s/%s\n"
        "Table:     %s\n\n" % (optype, label, table, optype, table))
    return path


def make_shelf(path, tool="mfx_dummy", label="Dummy", submenu="MFX Tools"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SHELF_XML % {"tool": tool, "label": label,
                                 "submenu": submenu})
    return path


def zip_dir(srcdir, dstzip):
    srcdir, dstzip = Path(srcdir), Path(dstzip)
    with zipfile.ZipFile(dstzip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(srcdir.rglob("*")):
            z.write(f, f.relative_to(srcdir))
    return dstzip


def make_camrig_zip(dstdir, feed_url=""):
    """Mimics the real MFX CamRig client zip: hda/ + installer/ + mfx.json."""
    dstdir = Path(dstdir)
    tree = dstdir / "camrig_src" / "MFX_CamRig"
    make_dummy_hda(tree / "hda" / "mfx_camrig_2.0.hda",
                   table="Object", optype="mfx::camrig::2.0",
                   label="MFX CamRig")
    (tree / "installer").mkdir(parents=True, exist_ok=True)
    (tree / "installer" / "install.py").write_text("# legacy fallback\n")
    manifest = {"name": "MFX CamRig", "version": "2.0",
                "min_houdini": "21.0"}
    if feed_url:
        manifest["updates"] = feed_url
    (tree / "mfx.json").write_text(json.dumps(manifest))
    return zip_dir(tree.parent, dstdir / "mfx_camrig_fx_2.0.zip")


def make_labs_tree(dstdir):
    """Mimics SideFXLabs: ships its own package json with an env var."""
    tree = Path(dstdir) / "SideFXLabs"
    make_dummy_hda(tree / "otls" / "labs_tool.hda",
                   table="Sop", optype="labs::tool::1.0", label="Labs Tool")
    make_shelf(tree / "toolbar" / "labs.shelf", tool="labs_tool",
               label="Labs Tool", submenu="Labs")
    (tree / "packages").mkdir(parents=True, exist_ok=True)
    (tree / "packages" / "SideFXLabs.json").write_text(json.dumps(
        {"env": [{"SIDEFXLABS": str(tree)}], "path": "$SIDEFXLABS"}))
    return tree


def make_gumroad_zip(dstdir):
    """The ugly case: wrapper dir, bare hda, junk name."""
    dstdir = Path(dstdir)
    tree = dstdir / "gum_src" / "MyTool_v2"
    make_dummy_hda(tree / "supertool_1.5.hda", table="Sop",
                   optype="super::tool::1.5", label="Super Tool")
    return zip_dir(tree.parent, dstdir / "MyTool_v2_FINAL(1).zip")
