import json, subprocess, sys, unittest, zipapp
from pathlib import Path

from util import REPO, Sandbox, SandboxCase


def build_pyz(dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    zipapp.create_archive(str(REPO / "src"), str(dest),
                          main="mfx.__main__:main",
                          interpreter="/usr/bin/env python3")
    return dest


class TestSelfUpdate(SandboxCase, unittest.TestCase):
    def test_self_update_replaces_pyz(self):
        old = build_pyz(self.sb.home / "bin" / "mfx.pyz")
        new = self.sb.home / "new.pyz"
        new.write_bytes(b"NEWPYZ")            # content only needs to differ
        feed = self.sb.home / "depot_feed.json"
        feed.write_text(json.dumps({"latest": "99.0",
                                    "url": new.resolve().as_uri(),
                                    "changelog": "shiny"}))
        r = self.sb.mfx("self-update", "--yes", env_extra={
            "MFX_DEPOT_FEED": feed.resolve().as_uri(),
            "MFX_SELF_PATH": str(old)})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("shiny", r.stdout)
        self.assertEqual(old.read_bytes(), b"NEWPYZ")

    def test_self_update_up_to_date(self):
        old = build_pyz(self.sb.home / "bin" / "mfx.pyz")
        feed = self.sb.home / "depot_feed.json"
        feed.write_text(json.dumps({"latest": "0.0.1", "url": ""}))
        r = self.sb.mfx("self-update", "--yes", env_extra={
            "MFX_DEPOT_FEED": feed.resolve().as_uri(),
            "MFX_SELF_PATH": str(old)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("up to date", r.stdout)

    def test_self_update_from_checkout_refuses(self):
        r = self.sb.mfx("self-update", "--yes")   # MFX_SELF_PATH unset
        self.assertEqual(r.returncode, 1)
        self.assertIn("git", r.stderr)

    def test_built_pyz_actually_runs(self):
        pyz = build_pyz(self.sb.home / "bin" / "mfx.pyz")
        r = subprocess.run([sys.executable, str(pyz), "--version"],
                           capture_output=True, text=True, env=self.sb.env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mfx", r.stdout)


if __name__ == "__main__":
    unittest.main()
