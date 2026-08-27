import json, tempfile, unittest
from pathlib import Path

from mfx import infer
from mfx.errors import DepotError
from util import REPO  # noqa: F401


def tree(spec, base=None):
    """Build a dir tree from {relpath: content}; dirs end with '/'. """
    base = base or Path(tempfile.mkdtemp(prefix="mfxinf_"))
    for rel, content in spec.items():
        p = base / rel
        if rel.endswith("/"):
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
    return base


class TestFindRoot(unittest.TestCase):
    def test_direct_otls_dir(self):
        t = tree({"otls/x.hda": "x"})
        self.assertEqual(infer.find_root(t), t)

    def test_descends_single_dir_wrappers(self):
        t = tree({"repo-main/hda/x.hda": "x"})
        self.assertEqual(infer.find_root(t), t / "repo-main")

    def test_bare_hda_at_top(self):
        t = tree({"tool.hda": "x"})
        self.assertEqual(infer.find_root(t), t)

    def test_shipped_packages_dir_is_marker(self):
        t = tree({"packages/SideFXLabs.json": "{}", "readme.md": "hi"})
        self.assertEqual(infer.find_root(t), t)

    def test_no_package_returns_none(self):
        t = tree({"docs/readme.md": "hi", "src/x.py": "pass"})
        self.assertIsNone(infer.find_root(t))


class TestNameVersion(unittest.TestCase):
    def test_split(self):
        self.assertEqual(infer.split_name_version("mfx_camrig_2.0"),
                         ("mfx_camrig", "2.0"))
        self.assertEqual(infer.split_name_version("MyTool_v2.1_FINAL(1)"),
                         ("MyTool", "2.1"))
        self.assertEqual(infer.split_name_version("plainname"),
                         ("plainname", None))


class TestInspect(unittest.TestCase):
    def test_manifest_wins(self):
        t = tree({"otls/x.hda": "x", "mfx.json": json.dumps(
            {"name": "MFX CamRig", "version": "2.0", "min_houdini": "21.0",
             "updates": "https://example.com/camrig.json"})})
        info = infer.inspect(t)
        self.assertEqual((info.name, info.slug, info.version),
                         ("MFX CamRig", "camrig", "2.0"))
        self.assertEqual(info.env_var, "MFX_CAMRIG")
        self.assertEqual(info.min_houdini, "21.0")
        self.assertEqual(info.feed, "https://example.com/camrig.json")
        self.assertFalse(info.unversioned)

    def test_shipped_pkg_json_names_package(self):
        t = tree({"otls/x.hda": "x", "packages/SideFXLabs.json":
                  json.dumps({"env": [{"SIDEFXLABS": "/x"}], "path": "$SIDEFXLABS"})})
        info = infer.inspect(t)
        self.assertEqual(info.name, "SideFXLabs")
        self.assertEqual(info.shipped_pkg, t / "packages" / "SideFXLabs.json")

    def test_hda_filename_fallback_and_hints(self):
        t = tree({"otls/supertool_1.5.hda": "x"})
        info = infer.inspect(t, name_hint="ignored-when-hda-has-name")
        self.assertEqual(info.version, "1.5")
        info2 = infer.inspect(t, override_name="Nice Name")
        self.assertEqual((info2.name, info2.slug), ("Nice Name", "nice-name"))

    def test_unversioned_gets_date_fallback(self):
        t = tree({"otls/tool.hda": "x"})
        info = infer.inspect(t, name_hint="tool")
        self.assertTrue(info.unversioned)
        self.assertRegex(info.version, r"^0\.0\+\d{8}$")

    def test_bad_manifest_is_actionable(self):
        t = tree({"otls/x.hda": "x", "mfx.json": "{nope"})
        with self.assertRaises(DepotError) as cm:
            infer.inspect(t)
        self.assertIn("mfx.json", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
