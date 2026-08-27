import json, unittest
from util import Sandbox, SandboxCase
import fixtures


class TestRollback(SandboxCase, unittest.TestCase):
    def _install_two_versions(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        assert self.sb.mfx("install", str(z), "--yes").returncode == 0
        tree = self.sb.home / "camrig_src"
        man = tree / "MFX_CamRig" / "mfx.json"
        man.write_text(json.dumps({"name": "MFX CamRig", "version": "2.1",
                                   "min_houdini": "21.0"}))
        z21 = fixtures.zip_dir(tree, self.sb.home / "camrig_2.1.zip")
        assert self.sb.mfx("install", str(z21), "--yes").returncode == 0

    def test_rollback_repoints_to_previous(self):
        self._install_two_versions()
        r = self.sb.mfx("rollback", "camrig", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("2.1 -> 2.0", r.stdout)
        f = self.sb.prefs21 / "packages" / "MFX_camrig.json"
        env = json.loads(f.read_text())["env"][0]["MFX_CAMRIG"]
        self.assertTrue(env.endswith("/camrig/2.0"), env)
        r = self.sb.mfx("list")
        self.assertIn("2.0", r.stdout)

    def test_rollback_single_version_is_actionable(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        r = self.sb.mfx("rollback", "camrig", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("at least two", r.stderr)

    def test_rollback_twice_hits_oldest(self):
        self._install_two_versions()
        self.sb.mfx("rollback", "camrig", "--yes")
        r = self.sb.mfx("rollback", "camrig", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("oldest", r.stderr)


if __name__ == "__main__":
    unittest.main()
