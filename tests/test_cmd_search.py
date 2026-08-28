import json, unittest
from util import Sandbox, SandboxCase
import fixtures

CAT = {"schema": 1, "packages": [
    {"slug": "vibrate", "name": "MFX Vibrate", "type": "free",
     "description": "Layered vibration SOP", "source": "https://x/v",
     "tags": ["motion"], "verified": "2026-08-28"},
    {"slug": "camrig", "name": "MFX CamRig", "type": "commercial",
     "description": "Camera rig", "buy_url": "https://x/buy",
     "tags": ["camera"]},
]}


class TestSearch(SandboxCase, unittest.TestCase):
    def _cat_env(self, cat=CAT):
        f = self.sb.home / "catalog.json"
        f.write_text(json.dumps(cat))
        return {"MFX_CATALOG_URL": f.resolve().as_uri()}

    def test_full_listing_and_term(self):
        env = self._cat_env()
        r = self.sb.mfx("search", env_extra=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("vibrate", r.stdout)
        self.assertIn("commercial", r.stdout)
        self.assertIn("verified 2026-08-28", r.stdout)
        r = self.sb.mfx("search", "camera", env_extra=env)
        self.assertIn("camrig", r.stdout)
        self.assertNotIn("vibrate", r.stdout)

    def test_no_match_hint(self):
        r = self.sb.mfx("search", "zzz", env_extra=self._cat_env())
        self.assertEqual(r.returncode, 0)
        self.assertIn("No catalog entries match", r.stdout)

    def test_installed_marker(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        r = self.sb.mfx("search", "camrig", env_extra=self._cat_env())
        self.assertIn("installed 2.0", r.stdout)

    def test_cache_fallback_note(self):
        env = self._cat_env()
        self.sb.mfx("search", env_extra=env)          # primes cache
        r = self.sb.mfx("search", env_extra={
            "MFX_CATALOG_URL": "file:///nonexistent/catalog.json"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cached", r.stdout)
        self.assertIn("vibrate", r.stdout)

    def test_no_cache_no_network_is_actionable(self):
        r = self.sb.mfx("search", env_extra={
            "MFX_CATALOG_URL": "file:///nonexistent/catalog.json"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("catalog", r.stderr)


if __name__ == "__main__":
    unittest.main()
