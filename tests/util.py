"""Shared harness: run the real mfx CLI in a disposable HOME."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))   # for direct-import unit tests


class Sandbox:
    def __init__(self):
        self.home = Path(tempfile.mkdtemp(prefix="mfxtest_"))
        self.prefs21 = self.home / "prefs" / "21.0"
        self.prefs22 = self.home / "prefs" / "22.0"
        for p in (self.prefs21, self.prefs22):
            p.mkdir(parents=True)

    def env(self, **extra):
        e = dict(os.environ)
        e["HOME"] = str(self.home)
        e["USERPROFILE"] = str(self.home)          # Windows Path.home()
        e["HOUDINI_USER_PREF_DIR"] = str(self.home / "prefs" / "__HVER__")
        e["PYTHONPATH"] = str(REPO / "src")
        e.pop("MFX_ROOT", None)
        e.update(extra)
        return e

    def mfx(self, *args, env_extra=None, input=None):
        return subprocess.run(
            [sys.executable, "-m", "mfx"] + [str(a) for a in args],
            capture_output=True, text=True, input=input,
            env=self.env(**(env_extra or {})))

    def cleanup(self):
        shutil.rmtree(self.home, ignore_errors=True)


class SandboxCase:
    """Mixin: unittest.TestCase with a fresh Sandbox per test."""
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.cleanup()
