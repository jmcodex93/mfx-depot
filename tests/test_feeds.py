import json, tempfile, unittest
from pathlib import Path

from mfx import feeds
from util import REPO  # noqa: F401


class TestFeeds(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mfxfeed_"))

    def _feed(self, data):
        f = self.tmp / "feed.json"
        f.write_text(json.dumps(data))
        return f.resolve().as_uri()

    def test_parse_version(self):
        self.assertEqual(feeds.parse_version("2.0"), (2, 0))
        self.assertEqual(feeds.parse_version("v2.1.3"), (2, 1, 3))
        self.assertEqual(feeds.parse_version("0.0+20260827"), (0, 0, 20260827))
        self.assertEqual(feeds.parse_version(None), (0,))
        self.assertTrue(feeds.parse_version("2.1") > feeds.parse_version("2.0"))

    def test_check_newer_via_feed(self):
        url = self._feed({"latest": "2.1", "url": "https://x/z.zip",
                          "changelog": "fixes"})
        entry = {"version": "2.0", "feed": url, "pin": None,
                 "source": {"kind": "local", "ref": "x"}}
        r = feeds.check(entry)
        self.assertTrue(r["newer"])
        self.assertEqual(r["latest"], "2.1")
        self.assertEqual(r["changelog"], "fixes")

    def test_check_legacy_minimal_feed(self):
        # the {latest, url} feeds already live for camrig/vibrate
        url = self._feed({"latest": "1.0", "url": ""})
        entry = {"version": "1.0", "feed": url, "pin": None,
                 "source": {"kind": "local", "ref": "x"}}
        r = feeds.check(entry)
        self.assertFalse(r["newer"])

    def test_check_no_feed_no_github_returns_none(self):
        entry = {"version": "1.0", "feed": None, "pin": None,
                 "source": {"kind": "local", "ref": "x.zip"}}
        self.assertIsNone(feeds.check(entry))

    def test_check_network_error_is_soft(self):
        entry = {"version": "1.0", "feed": "file:///nonexistent/f.json",
                 "pin": None, "source": {"kind": "local", "ref": "x"}}
        r = feeds.check(entry)
        self.assertIn("error", r)


if __name__ == "__main__":
    unittest.main()
