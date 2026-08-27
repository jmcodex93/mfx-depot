import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock

from mfx import sources
from mfx.errors import DepotError
from util import REPO  # noqa: F401
import fixtures


class TestUrlSources(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mfxurl_"))
        self.work = self.tmp / "work"
        self.work.mkdir()

    def _fileurl(self, p):
        return Path(p).resolve().as_uri()

    def test_direct_zip_url(self):
        z = fixtures.make_gumroad_zip(self.tmp)
        root, hints = sources.acquire(self._fileurl(z), self.work)
        self.assertTrue((root / "MyTool_v2" / "supertool_1.5.hda").is_file())
        self.assertEqual(hints["name"], "MyTool")

    def test_github_release_flow(self):
        z = fixtures.make_camrig_zip(self.tmp)
        api = self.tmp / "api" / "repos" / "jmcodex93" / "mfx-camrig"
        (api / "releases").mkdir(parents=True)
        (api / "releases" / "latest").write_text(json.dumps({
            "tag_name": "v2.0",
            "assets": [{"name": z.name,
                        "browser_download_url": self._fileurl(z)}],
            "zipball_url": self._fileurl(z)}))
        with mock.patch.dict(os.environ,
                             {"MFX_GITHUB_API": self._fileurl(self.tmp / "api")}):
            root, hints = sources.acquire(
                "https://github.com/jmcodex93/mfx-camrig", self.work)
        self.assertEqual(hints, {"name": "mfx-camrig", "version": "2.0"})
        self.assertTrue((root / "MFX_CamRig" / "mfx.json").is_file())

    def test_github_tags_fallback(self):
        z = fixtures.make_gumroad_zip(self.tmp)
        api = self.tmp / "api" / "repos" / "o" / "r"
        api.mkdir(parents=True)
        # no releases/latest file -> urlopen raises -> falls back to tags
        (api / "tags").write_text(json.dumps(
            [{"name": "1.5", "zipball_url": self._fileurl(z)}]))
        with mock.patch.dict(os.environ,
                             {"MFX_GITHUB_API": self._fileurl(self.tmp / "api")}):
            root, hints = sources.acquire("https://github.com/o/r", self.work)
        self.assertEqual(hints["version"], "1.5")

    def test_download_failure_is_actionable(self):
        with self.assertRaises(DepotError) as cm:
            sources.download("file:///nonexistent/nope.zip",
                             self.work / "x.zip")
        self.assertIn("could not download", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
