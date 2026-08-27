import json, unittest

from util import Sandbox, SandboxCase
import fixtures


class TestInstallE2E(SandboxCase, unittest.TestCase):
    def test_install_camrig_zip(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        r = self.sb.mfx("install", str(z), "--yes")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("MFX CamRig 2.0", r.stdout)
        payload = self.sb.home / "MFX" / "camrig" / "2.0"
        self.assertTrue((payload / "hda" / "mfx_camrig_2.0.hda").is_file())
        for prefs in (self.sb.prefs21, self.sb.prefs22):
            f = prefs / "packages" / "MFX_camrig.json"
            self.assertTrue(f.is_file(), f)
            data = json.loads(f.read_text())
            self.assertEqual(data["enable"], "houdini_version >= '21.0'")

    def test_install_prompts_and_aborts_without_yes(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        r = self.sb.mfx("install", str(z), input="n\n")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Nothing was changed", r.stdout)
        self.assertFalse((self.sb.home / "MFX" / "camrig").exists())

    def test_reinstall_same_slug_shows_update_summary(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        r = self.sb.mfx("install", str(z), "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("replaces: MFX CamRig 2.0", r.stdout)

    def test_install_gumroad_zip_name_from_zip_version_from_hda(self):
        z = fixtures.make_gumroad_zip(self.sb.home)
        r = self.sb.mfx("install", str(z), "--yes")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        # name from the cleaned zip stem (MyTool), version from the hda (1.5)
        self.assertTrue(
            (self.sb.home / "MFX" / "mytool" / "1.5").is_dir())

    def test_install_no_package_found_is_actionable(self):
        junk = self.sb.home / "src"
        (junk / "docs").mkdir(parents=True)
        (junk / "docs" / "readme.md").write_text("hi")
        r = self.sb.mfx("install", str(junk), "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no Houdini package found", r.stderr)

    def test_list_and_info(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        r = self.sb.mfx("list")
        self.assertEqual(r.returncode, 0)
        self.assertIn("camrig", r.stdout)
        self.assertIn("2.0", r.stdout)
        r = self.sb.mfx("info", "camrig")
        self.assertEqual(r.returncode, 0)
        self.assertIn("MFX_CAMRIG", r.stdout)
        r = self.sb.mfx("info", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not installed", r.stderr)

    def test_list_adopts_legacy_install(self):
        # simulate a CamRig installed by the legacy install.py
        tgt = self.sb.home / "MFX" / "CamRig" / "2.0"
        (tgt / "otls").mkdir(parents=True)
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "MFXCamRig.json").write_text(json.dumps(
            {"env": [{"MFX_CAMRIG": str(tgt)}], "path": "$MFX_CAMRIG"}))
        r = self.sb.mfx("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("camrig", r.stdout)
        self.assertIn("(adopted)", r.stdout)

    def test_list_all_shows_foreign_packages(self):
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "SideFXLabs.json").write_text(
            json.dumps({"env": [{"SIDEFXLABS": "/x"}], "path": "$SIDEFXLABS"}))
        r = self.sb.mfx("list", "--all")
        self.assertEqual(r.returncode, 0)
        self.assertIn("SideFXLabs.json", r.stdout)
        self.assertIn("foreign", r.stdout)


if __name__ == "__main__":
    unittest.main()
