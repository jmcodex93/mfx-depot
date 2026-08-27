import json, unittest
from util import Sandbox, SandboxCase
import fixtures


class TestDoctor(SandboxCase, unittest.TestCase):
    def test_clean_install_reports_no_problems(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("No problems found", r.stdout)

    def test_duplicate_hda_definitions_error(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        self.sb.mfx("install", str(z), "--name", "Copy Two", "--yes")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("mfx::camrig::2.0", r.stdout)
        self.assertIn("keep one", r.stdout)

    def test_shelf_collision_warns(self):
        t1 = fixtures.make_labs_tree(self.sb.home / "a")
        self.sb.mfx("install", str(t1), "--yes")
        t2 = fixtures.make_labs_tree(self.sb.home / "b")
        self.sb.mfx("install", str(t2), "--name", "Labs Clone", "--yes")
        r = self.sb.mfx("doctor")
        self.assertIn("labs_tool", r.stdout)
        self.assertIn("TAB", r.stdout)

    def test_broken_package_file_error(self):
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "broken.json").write_text("{nope")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("broken.json", r.stdout)
        self.assertIn("fix the JSON or delete", r.stdout)

    def test_dangling_foreign_env_path_error(self):
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "Ghost.json").write_text(json.dumps(
            {"env": [{"GHOST": str(self.sb.home / "nope")}],
             "path": "$GHOST"}))
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not exist", r.stdout)

    def test_missing_payload_error(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        import shutil
        shutil.rmtree(self.sb.home / "MFX" / "camrig")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("mfx repair", r.stdout)


if __name__ == "__main__":
    unittest.main()
