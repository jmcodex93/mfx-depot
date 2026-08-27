import json, os, stat, tempfile, unittest
from pathlib import Path
from unittest import mock

from mfx import infer, installer, registry
from mfx.errors import DepotError
from util import REPO  # noqa: F401
import fixtures


class InstallerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mfxinst_"))
        patcher = mock.patch.dict(os.environ, {"MFX_ROOT": str(self.tmp / "MFX")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.prefs = [self.tmp / "prefs" / "21.0", self.tmp / "prefs" / "22.0"]
        for p in self.prefs:
            p.mkdir(parents=True)


class TestRender(InstallerBase):
    def test_synthesized_package(self):
        tree = self.tmp / "t"
        fixtures.make_dummy_hda(tree / "otls" / "x_1.0.hda")
        (tree / "mfx.json").write_text(json.dumps(
            {"name": "Thing", "version": "1.0", "min_houdini": "21.0"}))
        info = infer.inspect(tree)
        data = installer.render_pkg_json(info, Path("/inst/thing/1.0"))
        self.assertEqual(data["env"], [{"MFX_THING": "/inst/thing/1.0"}])
        self.assertEqual(data["path"], "$MFX_THING")
        self.assertEqual(data["enable"], "houdini_version >= '21.0'")

    def test_shipped_template_rewritten(self):
        tree = fixtures.make_labs_tree(self.tmp)
        info = infer.inspect(tree)
        target = Path("/inst/SideFXLabs/1.0")
        data = installer.render_pkg_json(info, target)
        self.assertEqual(data["env"], [{"SIDEFXLABS": str(target)}])
        self.assertEqual(data["path"], "$SIDEFXLABS")   # tokens untouched

    def test_stale_absolute_creator_path_repointed(self):
        # creator shipped their own machine's absolute path: repoint it
        tree = self.tmp / "ship"
        fixtures.make_dummy_hda(tree / "otls" / "x.hda")
        (tree / "packages").mkdir(parents=True, exist_ok=True)
        (tree / "packages" / "Tool.json").write_text(json.dumps(
            {"env": [{"TOOL": "/Users/creator/dev/Tool"}], "path": "$TOOL"}))
        info = infer.inspect(tree)
        data = installer.render_pkg_json(info, Path("/inst/tool/1.0"))
        self.assertEqual(data["env"], [{"TOOL": "/inst/tool/1.0"}])


class TestApply(InstallerBase):
    def _info(self):
        tree = self.tmp / "src_pkg"
        fixtures.make_dummy_hda(tree / "otls" / "thing_1.0.hda")
        return infer.inspect(tree, name_hint="thing")

    def test_apply_installs_and_registers(self):
        reg = registry.load()
        info = self._info()
        target = installer.apply(info, reg, self.prefs,
                                 {"kind": "folder", "ref": "src_pkg"})
        self.assertTrue((target / "otls" / "thing_1.0.hda").is_file())
        self.assertEqual(target, registry.mfx_root() / "thing" / "1.0")
        for p in self.prefs:
            f = p / "packages" / "MFX_thing.json"
            self.assertTrue(f.is_file())
            self.assertEqual(json.loads(f.read_text())["env"],
                             [{"MFX_THING": str(target)}])
        e = reg["packages"]["thing"]
        self.assertEqual(e["version"], "1.0")
        self.assertEqual(e["pkg_data"]["path"], "$MFX_THING")
        self.assertIn("1.0", e["versions"])

    def test_existing_pkg_file_backed_up(self):
        f = self.prefs[0] / "packages" / "MFX_thing.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('{"old": true}')
        reg = registry.load()
        installer.apply(self._info(), reg, self.prefs,
                        {"kind": "folder", "ref": "x"})
        baks = list(registry.backups_dir().rglob("*MFX_thing.json"))
        self.assertEqual(len(baks), 1)
        self.assertIn("old", baks[0].read_text())

    def test_registration_failure_rolls_back(self):
        f0 = self.prefs[0] / "packages" / "MFX_thing.json"
        f0.parent.mkdir(parents=True, exist_ok=True)
        f0.write_text('{"old": true}')
        # make the SECOND prefs dir unwritable so the transaction fails late
        (self.prefs[1] / "packages").mkdir(parents=True, exist_ok=True)
        os.chmod(self.prefs[1] / "packages", stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, self.prefs[1] / "packages", 0o755)
        reg = registry.load()
        with self.assertRaises(DepotError) as cm:
            installer.apply(self._info(), reg, self.prefs,
                            {"kind": "folder", "ref": "x"})
        self.assertIn("rolled back", str(cm.exception))
        self.assertEqual(json.loads(f0.read_text()), {"old": True})


if __name__ == "__main__":
    unittest.main()
