import json, shutil, unittest
from util import Sandbox, SandboxCase
import fixtures


class TestUninstallRepair(SandboxCase, unittest.TestCase):
    def _install_camrig(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        r = self.sb.mfx("install", str(z), "--yes")
        assert r.returncode == 0, r.stderr
        return self.sb.home / "MFX" / "camrig"

    def test_uninstall_removes_pkg_files_keeps_payload(self):
        payload = self._install_camrig()
        r = self.sb.mfx("uninstall", "camrig", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        for prefs in (self.sb.prefs21, self.sb.prefs22):
            self.assertFalse((prefs / "packages" / "MFX_camrig.json").exists())
        self.assertTrue(payload.is_dir())          # kept without --purge
        self.assertIn("kept", r.stdout)
        r = self.sb.mfx("list")
        self.assertNotIn("camrig", r.stdout)

    def test_uninstall_purge_deletes_payload(self):
        payload = self._install_camrig()
        r = self.sb.mfx("uninstall", "camrig", "--purge", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(payload.exists())

    def test_uninstall_unknown_is_actionable(self):
        r = self.sb.mfx("uninstall", "nope", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not installed", r.stderr)

    def test_repair_rewrites_deleted_pkg_file(self):
        self._install_camrig()
        f = self.sb.prefs21 / "packages" / "MFX_camrig.json"
        f.unlink()
        r = self.sb.mfx("repair", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(f.is_file())
        self.assertEqual(json.loads(f.read_text())["path"], "$MFX_CAMRIG")

    def test_repair_reports_missing_payload(self):
        payload = self._install_camrig()
        shutil.rmtree(payload)
        r = self.sb.mfx("repair", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing on disk", r.stdout + r.stderr)
        self.assertIn("mfx install", r.stdout + r.stderr)  # suggested fix

    def test_repair_unknown_is_actionable(self):
        r = self.sb.mfx("repair", "nope", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not installed", r.stderr)


if __name__ == "__main__":
    unittest.main()
