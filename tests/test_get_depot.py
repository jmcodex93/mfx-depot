import subprocess, sys, unittest
from pathlib import Path

from util import REPO, Sandbox, SandboxCase
from test_selfupdate import build_pyz


class TestGetDepot(SandboxCase, unittest.TestCase):
    def test_bootstrap_installs_pyz_and_shims(self):
        stage = self.sb.home / "release"
        stage.mkdir()
        build_pyz(stage / "mfx.pyz")
        script = stage / "get-depot.py"
        script.write_text((REPO / "bin" / "get-depot.py").read_text())
        r = subprocess.run([sys.executable, str(script), "--yes"],
                           capture_output=True, text=True, env=self.sb.env())
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        bindir = self.sb.home / "MFX" / "depot" / "bin"
        self.assertTrue((bindir / "mfx.pyz").is_file())
        self.assertTrue((bindir / "mfx").is_file())
        self.assertTrue((bindir / "mfx.cmd").is_file())
        self.assertIn("PATH", r.stdout)
        # the installed shim actually runs
        r2 = subprocess.run(["sh", str(bindir / "mfx"), "--version"],
                            capture_output=True, text=True, env=self.sb.env())
        self.assertEqual(r2.returncode, 0, r2.stderr)

    def test_bootstrap_without_pyz_is_actionable(self):
        stage = self.sb.home / "empty"
        stage.mkdir()
        script = stage / "get-depot.py"
        script.write_text((REPO / "bin" / "get-depot.py").read_text())
        r = subprocess.run([sys.executable, str(script), "--yes"],
                           capture_output=True, text=True, env=self.sb.env())
        self.assertEqual(r.returncode, 1)
        self.assertIn("mfx.pyz", r.stderr)


if __name__ == "__main__":
    unittest.main()
