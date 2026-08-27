import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock

from mfx import registry
from mfx.errors import DepotError
from util import REPO  # noqa: F401


class RegistryBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mfxreg_"))
        patcher = mock.patch.dict(os.environ, {"MFX_ROOT": str(self.tmp / "MFX")})
        patcher.start()
        self.addCleanup(patcher.stop)


class TestState(RegistryBase):
    def test_load_missing_returns_empty_schema(self):
        self.assertEqual(registry.load(), {"schema": 1, "packages": {}})

    def test_save_then_load_roundtrip(self):
        data = registry.load()
        data["packages"]["x"] = {"name": "X"}
        registry.save(data)
        self.assertEqual(registry.load()["packages"]["x"]["name"], "X")
        self.assertTrue(registry.state_path().is_file())

    def test_corrupt_state_is_actionable(self):
        registry.save(registry.load())
        registry.state_path().write_text("{nope")
        with self.assertRaises(DepotError) as cm:
            registry.load()
        self.assertIn("mfx repair", str(cm.exception))

    def test_slugify(self):
        self.assertEqual(registry.slugify("MFX CamRig"), "camrig")
        self.assertEqual(registry.slugify("MyTool_v2 FINAL"), "mytool-v2-final")
        self.assertEqual(registry.slugify("mfx"), "mfx")   # bare brand kept
        with self.assertRaises(DepotError):
            registry.slugify("___")


class TestLoadsLax(unittest.TestCase):
    def test_comments_and_trailing_commas(self):
        self.assertEqual(registry.loads_lax(
            '{\n// hi\n"env": [\n  {"A": "1"},\n],\n}'),
            {"env": [{"A": "1"}]})

    def test_slashes_inside_strings_survive(self):
        self.assertEqual(registry.loads_lax('{"p": "http://x//y"}'),
                         {"p": "http://x//y"})

    def test_strict_json_unchanged(self):
        self.assertEqual(registry.loads_lax('{"a": 1}'), {"a": 1})

    def test_still_invalid_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            registry.loads_lax('{"env": [}')


class TestAdoption(RegistryBase):
    def _legacy_prefs(self, name="MFXCamRig.json", var="MFX_CAMRIG",
                      target="CamRig/2.0"):
        prefs = self.tmp / "prefs" / "21.0"
        (prefs / "packages").mkdir(parents=True, exist_ok=True)
        tgt = registry.mfx_root() / target
        tgt.mkdir(parents=True, exist_ok=True)
        (prefs / "packages" / name).write_text(json.dumps(
            {"env": [{var: str(tgt)}], "path": "$" + var}))
        return prefs

    def test_adopts_legacy_camrig(self):
        prefs = self._legacy_prefs()
        data = registry.load()
        adopted = registry.adopt(data, [prefs])
        self.assertEqual(adopted, ["camrig"])
        e = data["packages"]["camrig"]
        self.assertEqual(e["version"], "2.0")
        self.assertEqual(e["payload_dir"], "CamRig")
        self.assertEqual(e["pkg_file"], "MFXCamRig.json")
        self.assertEqual(e["env_var"], "MFX_CAMRIG")
        self.assertEqual(e["source"]["kind"], "adopted")
        self.assertIn(str(prefs), e["prefs"])

    def test_adopt_is_idempotent_and_merges_prefs(self):
        p1 = self._legacy_prefs()
        data = registry.load()
        registry.adopt(data, [p1])
        registry.adopt(data, [p1])          # again: no dupes
        self.assertEqual(len(data["packages"]["camrig"]["prefs"]), 1)

    def test_ignores_foreign_and_broken_packages(self):
        prefs = self._legacy_prefs()
        (prefs / "packages" / "SideFXLabs.json").write_text(
            json.dumps({"env": [{"SIDEFXLABS": "/somewhere"}], "path": "$SIDEFXLABS"}))
        (prefs / "packages" / "broken.json").write_text("{nope")
        data = registry.load()
        self.assertEqual(registry.adopt(data, [prefs]), ["camrig"])

    def test_adopts_lax_json_package(self):
        prefs = self.tmp / "prefs" / "21.0"
        (prefs / "packages").mkdir(parents=True, exist_ok=True)
        tgt = registry.mfx_root() / "CamRig" / "2.0"
        tgt.mkdir(parents=True, exist_ok=True)
        (prefs / "packages" / "MFXCamRig.json").write_text(
            '{\n'
            '  // written by hand, Houdini accepts this\n'
            '  "env": [\n'
            '    {"MFX_CAMRIG": "%s"},\n'
            '  ],\n'
            '  "path": "$MFX_CAMRIG",\n'
            '}\n' % tgt)
        data = registry.load()
        self.assertEqual(registry.adopt(data, [prefs]), ["camrig"])

    def test_outside_mfx_root_not_adopted(self):
        prefs = self.tmp / "prefs" / "21.0"
        (prefs / "packages").mkdir(parents=True, exist_ok=True)
        (prefs / "packages" / "MFXOther.json").write_text(json.dumps(
            {"env": [{"MFX_OTHER": "/elsewhere/Other/1.0"}], "path": "$MFX_OTHER"}))
        data = registry.load()
        self.assertEqual(registry.adopt(data, [prefs]), [])


if __name__ == "__main__":
    unittest.main()
