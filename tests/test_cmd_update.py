import json, unittest
from pathlib import Path

from util import Sandbox, SandboxCase
import fixtures


class TestUpdatePin(SandboxCase, unittest.TestCase):
    def _install_with_feed(self):
        """Install camrig 2.0 whose mfx.json points at a local feed that
        advertises 2.1 (whose zip is also local)."""
        newer_dir = self.sb.home / "newer"
        z21 = fixtures.make_camrig_zip(newer_dir)
        # rewrite the 2.1 zip's manifest version by rebuilding the tree
        import zipfile, shutil
        tree = newer_dir / "camrig_src"
        man = tree / "MFX_CamRig" / "mfx.json"
        man.write_text(json.dumps({"name": "MFX CamRig", "version": "2.1",
                                   "min_houdini": "21.0"}))
        z21.unlink()
        z21 = fixtures.zip_dir(tree, newer_dir / "mfx_camrig_fx_2.1.zip")
        feed = self.sb.home / "camrig_feed.json"
        feed.write_text(json.dumps({"latest": "2.1",
                                    "url": z21.resolve().as_uri(),
                                    "changelog": "big fixes"}))
        z20 = fixtures.make_camrig_zip(self.sb.home,
                                       feed_url=feed.resolve().as_uri())
        r = self.sb.mfx("install", str(z20), "--yes")
        assert r.returncode == 0, r.stderr
        return feed

    def test_update_applies_newer_version(self):
        self._install_with_feed()
        r = self.sb.mfx("update", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("2.0 -> 2.1", r.stdout)
        self.assertIn("big fixes", r.stdout)
        self.assertTrue((self.sb.home / "MFX" / "camrig" / "2.1").is_dir())
        # old version stays on disk for rollback
        self.assertTrue((self.sb.home / "MFX" / "camrig" / "2.0").is_dir())

    def test_update_pinned_is_skipped(self):
        self._install_with_feed()
        r = self.sb.mfx("pin", "camrig")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.sb.mfx("update", "--yes")
        self.assertEqual(r.returncode, 0)
        self.assertIn("pinned", r.stdout)
        self.assertFalse((self.sb.home / "MFX" / "camrig" / "2.1").exists())
        r = self.sb.mfx("unpin", "camrig")
        self.assertEqual(r.returncode, 0)
        r = self.sb.mfx("update", "--yes")
        self.assertTrue((self.sb.home / "MFX" / "camrig" / "2.1").is_dir())

    def test_update_without_feeds_reports_nothing(self):
        z = fixtures.make_gumroad_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        r = self.sb.mfx("update", "--yes")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no update channel", r.stdout)

    def test_pin_other_version_is_actionable(self):
        self._install_with_feed()
        r = self.sb.mfx("pin", "camrig", "9.9")
        self.assertEqual(r.returncode, 1)
        self.assertIn("rollback", r.stderr)


if __name__ == "__main__":
    unittest.main()
