import json, unittest
from util import Sandbox, SandboxCase
import fixtures


class TestInstallByName(SandboxCase, unittest.TestCase):
    def _catalog_with_free_entry(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        cat = {"schema": 1, "packages": [
            {"slug": "camrig", "name": "MFX CamRig", "type": "free",
             "description": "rig", "source": z.resolve().as_uri(),
             "feed": "https://example.com/camrig.json",
             "min_houdini": "21.0"},
            {"slug": "modeler", "name": "Modeler", "type": "commercial",
             "description": "modeling env", "buy_url": "https://x/buy"},
        ]}
        f = self.sb.home / "catalog.json"
        f.write_text(json.dumps(cat))
        return {"MFX_CATALOG_URL": f.resolve().as_uri()}

    def test_install_free_entry_by_name(self):
        env = self._catalog_with_free_entry()
        r = self.sb.mfx("install", "camrig", "--yes", env_extra=env)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue((self.sb.home / "MFX" / "camrig" / "2.0").is_dir())
        r = self.sb.mfx("info", "camrig")
        # catalog feed recorded (zip's mfx.json carries none)
        self.assertIn("example.com/camrig.json", r.stdout)

    def test_commercial_entry_prints_buy_instructions(self):
        env = self._catalog_with_free_entry()
        r = self.sb.mfx("install", "modeler", "--yes", env_extra=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("https://x/buy", r.stdout)
        self.assertIn("After purchase", r.stdout)
        self.assertFalse((self.sb.home / "MFX" / "modeler").exists())

    def test_unknown_name_suggests_search(self):
        env = self._catalog_with_free_entry()
        r = self.sb.mfx("install", "nope", "--yes", env_extra=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("mfx search", r.stderr)

    def test_local_path_wins_over_catalog_slug(self):
        env = self._catalog_with_free_entry()
        # a local FOLDER named like a catalog slug: the path wins.
        # Proof: the local payload is version 9.9; the catalog's is 2.0.
        local = self.sb.home / "camrig"
        fixtures.make_dummy_hda(local / "otls" / "other_9.9.hda",
                                optype="other::tool::9.9")
        r = self.sb.mfx("install", str(local), "--yes", env_extra=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        # folder-name hint wins the NAME (slug camrig), hda supplies 9.9
        self.assertTrue((self.sb.home / "MFX" / "camrig" / "9.9").is_dir())
        self.assertFalse((self.sb.home / "MFX" / "camrig" / "2.0").exists())


if __name__ == "__main__":
    unittest.main()
