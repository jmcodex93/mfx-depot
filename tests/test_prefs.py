import os, tempfile, unittest
from pathlib import Path
from unittest import mock

from mfx import prefs
from mfx.errors import DepotError
from util import REPO  # noqa: F401  (imports set sys.path to src/)


class TestPrefsDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mfxprefs_"))
        (self.tmp / "prefs" / "21.0").mkdir(parents=True)
        (self.tmp / "prefs" / "22.0").mkdir(parents=True)
        (self.tmp / "prefs" / "20.5").mkdir(parents=True)   # below floor
        (self.tmp / "prefs" / "junk").mkdir(parents=True)   # no version

    def _with_env(self, **env):
        return mock.patch.dict(os.environ, env, clear=False)

    def test_custom_pref_dir_with_hver_token(self):
        with self._with_env(HOUDINI_USER_PREF_DIR=str(self.tmp / "prefs" / "__HVER__")), \
             mock.patch('pathlib.Path.home', return_value=self.tmp):
            dirs = prefs.houdini_pref_dirs()
        names = sorted(d.name for d in dirs)
        self.assertEqual(names, ["21.0", "22.0"])   # 20.5 and junk excluded

    def test_extra_dir_appended_and_deduped(self):
        extra = self.tmp / "prefs" / "21.0"
        with self._with_env(HOUDINI_USER_PREF_DIR=str(self.tmp / "prefs" / "__HVER__")), \
             mock.patch('pathlib.Path.home', return_value=self.tmp):
            dirs = prefs.houdini_pref_dirs(extra=str(extra))
        self.assertEqual(len([d for d in dirs if d.resolve() == extra.resolve()]), 1)

    def test_missing_extra_dir_raises_actionable(self):
        with self._with_env(HOUDINI_USER_PREF_DIR=str(self.tmp / "prefs" / "__HVER__")), \
             mock.patch('pathlib.Path.home', return_value=self.tmp):
            with self.assertRaises(DepotError) as cm:
                prefs.houdini_pref_dirs(extra=str(self.tmp / "nope"))
        self.assertIn("does not exist", str(cm.exception))

    def test_none_found_raises_actionable(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self._with_env(HOUDINI_USER_PREF_DIR=str(empty / "__HVER__"),
                            HOME=str(empty), USERPROFILE=str(empty)):
            with self.assertRaises(DepotError) as cm:
                prefs.houdini_pref_dirs()
        self.assertIn("Launch Houdini once", str(cm.exception))

    def test_pkg_dir(self):
        self.assertEqual(prefs.pkg_dir(Path("/x/21.0")), Path("/x/21.0/packages"))


if __name__ == "__main__":
    unittest.main()
