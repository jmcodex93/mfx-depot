import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock

from mfx import catalog
from mfx.errors import DepotError
from util import REPO  # noqa: F401  (puts src/ on sys.path)

CAT = {"schema": 1, "packages": [
    {"slug": "vibrate", "name": "MFX Vibrate", "type": "free",
     "description": "Layered vibration SOP", "source": "https://x/v",
     "feed": "https://x/vibrate.json", "min_houdini": "21.0",
     "tags": ["motion", "sop"], "verified": "2026-08-28"},
    {"slug": "camrig", "name": "MFX CamRig", "type": "commercial",
     "description": "Camera rig", "buy_url": "https://x/buy",
     "tags": ["camera"]},
    {"name": "no-slug-entry-skipped"},
]}


class CatalogBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mfxcat_"))
        patcher = mock.patch.dict(os.environ, {"MFX_ROOT": str(self.tmp / "MFX")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _serve(self, obj_or_text):
        f = self.tmp / "catalog.json"
        f.write_text(obj_or_text if isinstance(obj_or_text, str)
                     else json.dumps(obj_or_text))
        os.environ["MFX_CATALOG_URL"] = f.resolve().as_uri()
        self.addCleanup(os.environ.pop, "MFX_CATALOG_URL", None)
        return f


class TestFetch(CatalogBase):
    def test_fetch_parses_and_caches(self):
        self._serve(CAT)
        data, cached = catalog.fetch()
        self.assertFalse(cached)
        self.assertEqual(len(data["packages"]), 3)
        self.assertTrue(catalog.cache_path().is_file())

    def test_network_failure_falls_back_to_cache(self):
        self._serve(CAT)
        catalog.fetch()                       # primes the cache
        os.environ["MFX_CATALOG_URL"] = "file:///nonexistent/catalog.json"
        data, cached = catalog.fetch()
        self.assertTrue(cached)
        self.assertEqual(data["packages"][0]["slug"], "vibrate")

    def test_network_failure_without_cache_is_actionable(self):
        os.environ["MFX_CATALOG_URL"] = "file:///nonexistent/catalog.json"
        self.addCleanup(os.environ.pop, "MFX_CATALOG_URL", None)
        with self.assertRaises(DepotError) as cm:
            catalog.fetch()
        self.assertIn("catalog", str(cm.exception))
        self.assertIn("connection", str(cm.exception))

    def test_malformed_remote_is_actionable_not_cached(self):
        self._serve(CAT)
        catalog.fetch()                       # good cache exists
        f = self._serve("{nope")
        with self.assertRaises(DepotError) as cm:
            catalog.fetch()                   # malformed remote NEVER falls back
        self.assertIn(f.resolve().as_uri(), str(cm.exception))

    def test_wrong_shape_is_actionable(self):
        self._serve({"schema": 1, "packages": "not-a-list"})
        with self.assertRaises(DepotError) as cm:
            catalog.fetch()
        self.assertIn("unexpected format", str(cm.exception))


class TestFindResolve(CatalogBase):
    def test_find_all_and_by_term(self):
        self.assertEqual(len(catalog.find(CAT)), 2)      # slugless skipped
        self.assertEqual(catalog.find(CAT, "camera")[0]["slug"], "camrig")
        self.assertEqual(catalog.find(CAT, "SOP")[0]["slug"], "vibrate")
        self.assertEqual(catalog.find(CAT, "zzz"), [])

    def test_resolve_slug_then_unique_name(self):
        self.assertEqual(catalog.resolve(CAT, "vibrate")["slug"], "vibrate")
        self.assertEqual(catalog.resolve(CAT, "mfx camrig")["slug"], "camrig")
        self.assertIsNone(catalog.resolve(CAT, "nope"))


if __name__ == "__main__":
    unittest.main()
