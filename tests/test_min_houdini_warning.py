import json, unittest
from util import Sandbox, SandboxCase
import fixtures


class TestMinHoudiniWarning(SandboxCase, unittest.TestCase):
    def test_warns_on_prefs_below_min(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        # bump the manifest's floor above both sandbox prefs (21.0/22.0)
        tree = self.sb.home / "camrig_src"
        man = tree / "MFX_CamRig" / "mfx.json"
        man.write_text(json.dumps({"name": "MFX CamRig", "version": "2.0",
                                   "min_houdini": "23.0"}))
        z = fixtures.zip_dir(tree, self.sb.home / "camrig_23.zip")
        r = self.sb.mfx("install", str(z), "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("needs Houdini 23.0+", r.stdout)
        self.assertIn("21.0", r.stdout)

    def test_no_warning_when_satisfied(self):
        z = fixtures.make_camrig_zip(self.sb.home)   # min 21.0
        r = self.sb.mfx("install", str(z), "--yes")
        self.assertNotIn("needs Houdini", r.stdout)

    def test_list_shows_depot_itself(self):
        # spec section 9: Depot appears in mfx list like any package
        r = self.sb.mfx("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("depot", r.stdout)
        self.assertIn("(self)", r.stdout)


if __name__ == "__main__":
    unittest.main()
