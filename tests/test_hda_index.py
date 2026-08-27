import tempfile, unittest
from pathlib import Path

from mfx.hda_index import operator_types
from mfx.errors import DepotError
from util import REPO  # noqa: F401
import fixtures

REAL_HDA = Path(__file__).parent / "fixtures" / "mfx_vibrate_1.0.hda"


class TestHdaIndex(unittest.TestCase):
    def test_real_production_hda(self):
        ops = operator_types(REAL_HDA)
        self.assertEqual(ops, [("Sop", "mfx::vibrate::1.0")])

    def test_binary_key_substring_false_positive_rejected(self):
        # "Sop" inside "StopSop" and "Shop" inside "BarShop" must not be
        # mistaken for a genuine "<Table>/<name>" section key -- there is
        # no real operator index here, so this must raise DepotError.
        tmp = Path(tempfile.mkdtemp(prefix="mfxidx_"))
        junk = tmp / "fake_keys.hda"
        junk.write_text("randomStopSop/xyz::1.0 tail\nFooBarShop/thing more\n")
        with self.assertRaises(DepotError) as cm:
            operator_types(junk)
        self.assertIn("no operator index", str(cm.exception))

    def test_dummy_fixture(self):
        tmp = Path(tempfile.mkdtemp(prefix="mfxidx_"))
        f = fixtures.make_dummy_hda(tmp / "x.hda", table="Object",
                                    optype="mfx::camrig::2.0")
        self.assertEqual(operator_types(f), [("Object", "mfx::camrig::2.0")])

    def test_dedup_preserves_order(self):
        tmp = Path(tempfile.mkdtemp(prefix="mfxidx_"))
        f = tmp / "multi.hda"
        f.write_text("Operator:  a::1.0\nTable:  Sop\n\n"
                     "Operator:  b::1.0\nTable:  Dop\n\n"
                     "Operator:  a::1.0\nTable:  Sop\n")
        self.assertEqual(operator_types(f),
                         [("Sop", "a::1.0"), ("Dop", "b::1.0")])

    def test_no_index_is_actionable(self):
        tmp = Path(tempfile.mkdtemp(prefix="mfxidx_"))
        junk = tmp / "junk.hda"
        junk.write_bytes(b"\x00\x01\x02 nothing here")
        with self.assertRaises(DepotError) as cm:
            operator_types(junk)
        self.assertIn("no operator index", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
