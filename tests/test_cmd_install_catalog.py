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

    def test_explicit_name_flag_beats_catalog_entry_name(self):
        # Finding 2: --name flag should take precedence over catalog entry name
        env = self._catalog_with_free_entry()
        # Catalog entry has name "MFX CamRig", but we override with --name
        r = self.sb.mfx("install", "camrig", "--name", "Other Name", "--yes",
                       env_extra=env)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        # Package should be installed under the slugified override name
        self.assertTrue((self.sb.home / "MFX" / "other-name" / "2.0").is_dir(),
                       "Package not found at expected slug 'other-name'")
        # Verify it's registered with the override name
        r = self.sb.mfx("info", "other-name")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Other Name", r.stdout)

    def test_free_entry_without_source_fails(self):
        # Finding 4: free entry missing source should raise actionable error
        z = fixtures.make_camrig_zip(self.sb.home)
        cat = {"schema": 1, "packages": [
            {"slug": "nosrc", "name": "NoSource", "type": "free",
             "description": "missing source field"}
            # Note: no "source" field
        ]}
        f = self.sb.home / "catalog.json"
        f.write_text(json.dumps(cat))
        env = {"MFX_CATALOG_URL": f.resolve().as_uri()}
        r = self.sb.mfx("install", "nosrc", "--yes", env_extra=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no source", r.stderr)
        # Catalog URL should be mentioned for reporting
        self.assertIn("catalog", r.stderr.lower())


if __name__ == "__main__":
    unittest.main()
