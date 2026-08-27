import tempfile, unittest, zipfile
from pathlib import Path

from mfx import sources
from mfx.errors import DepotError
from util import REPO  # noqa: F401
import fixtures


class TestAcquireLocal(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mfxsrc_"))
        self.work = self.tmp / "work"
        self.work.mkdir()

    def test_folder_passthrough(self):
        tree = fixtures.make_labs_tree(self.tmp)
        root, hints = sources.acquire(str(tree), self.work)
        self.assertEqual(root, tree)
        self.assertEqual(hints["name"], "SideFXLabs")

    def test_zip_extracted_with_name_hint_only(self):
        z = fixtures.make_gumroad_zip(self.tmp)
        root, hints = sources.acquire(str(z), self.work)
        self.assertTrue((root / "MyTool_v2" / "supertool_1.5.hda").is_file())
        self.assertEqual(hints["name"], "MyTool")
        self.assertNotIn("version", hints)   # zip digits are untrustworthy

    def test_bare_hda_wrapped_in_otls(self):
        hda = fixtures.make_dummy_hda(self.tmp / "supertool_1.5.hda")
        root, hints = sources.acquire(str(hda), self.work)
        self.assertTrue((root / "otls" / "supertool_1.5.hda").is_file())
        self.assertEqual(hints, {"name": "supertool", "version": "1.5"})

    def test_zip_slip_rejected(self):
        evil = self.tmp / "evil.zip"
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../outside.txt", "boom")
        with self.assertRaises(DepotError) as cm:
            sources.acquire(str(evil), self.work)
        self.assertIn("unsafe path", str(cm.exception))

    def test_missing_and_unknown_are_actionable(self):
        with self.assertRaises(DepotError):
            sources.acquire(str(self.tmp / "nope.zip"), self.work)
        junk = self.tmp / "x.txt"
        junk.write_text("hi")
        with self.assertRaises(DepotError) as cm:
            sources.acquire(str(junk), self.work)
        self.assertIn("expected a folder", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
