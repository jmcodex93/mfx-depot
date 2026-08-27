import json, os, unittest
from pathlib import Path
from unittest import mock

from util import REPO, Sandbox, SandboxCase
import fixtures


class TestMapRecords(unittest.TestCase):
    def test_mapping_pure(self):
        from mfx import lockfile
        with mock.patch.dict(os.environ, {"MFX_ROOT": "/mr"}):
            reg = {"packages": {"camrig": {
                "name": "MFX CamRig", "slug": "camrig", "version": "2.0",
                "payload_dir": "camrig"}}}
            payload = {"houdini": "21.0.792", "records": [
                {"type": "Object/mfx::camrig::2.0",
                 "library": "/mr/camrig/2.0/hda/mfx_camrig_2.0.hda"},
                {"type": "Object/mfx::camrig::2.0",     # dupe collapses
                 "library": "/mr/camrig/2.0/hda/mfx_camrig_2.0.hda"},
                {"type": "Sop/foo::1.0", "library": "/elsewhere/foo.hda"},
                {"type": "Sop/emb::1.0", "library": "Embedded"}]}
            lock = lockfile.map_records(payload, reg, "shot010.hip")
        self.assertEqual(lock["schema"], 1)
        self.assertEqual(lock["houdini"], "21.0.792")
        self.assertEqual(lock["packages"], [
            {"name": "MFX CamRig", "slug": "camrig", "version": "2.0",
             "types": ["Object/mfx::camrig::2.0"]}])
        self.assertEqual(lock["embedded"], ["Sop/emb::1.0"])
        self.assertEqual(lock["unresolved"],
                         [{"type": "Sop/foo::1.0",
                           "library": "/elsewhere/foo.hda"}])


class TestLockE2E(SandboxCase, unittest.TestCase):
    def _stub_hython(self, lib):
        """A fake hython: ignores the helper, prints a canned payload."""
        stub = self.sb.home / "hython"
        stub.write_text(
            "#!/usr/bin/env python3\nimport json\n"
            "print(json.dumps({'houdini': '21.0.792', 'records': ["
            "{'type': 'Object/mfx::camrig::2.0', 'library': %r},"
            "{'type': 'Sop/foo::1.0', 'library': '/elsewhere/foo.hda'},"
            "{'type': 'Sop/emb::1.0', 'library': 'Embedded'}]}))\n"
            % str(lib))
        stub.chmod(0o755)
        return stub

    def test_lock_end_to_end_with_stub(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        assert self.sb.mfx("install", str(z), "--yes").returncode == 0
        lib = (self.sb.home / "MFX" / "camrig" / "2.0" / "hda"
               / "mfx_camrig_2.0.hda")
        stub = self._stub_hython(lib)
        hip = self.sb.home / "shot010.hip"
        hip.write_bytes(b"fakehip")
        outj = self.sb.home / "lock.json"
        r = self.sb.mfx("lock", str(hip), "-o", str(outj),
                        env_extra={"MFX_HYTHON": str(stub)})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        lock = json.loads(outj.read_text())
        self.assertEqual(lock["packages"][0]["slug"], "camrig")
        self.assertEqual(lock["embedded"], ["Sop/emb::1.0"])
        self.assertEqual(len(lock["unresolved"]), 1)
        self.assertIn("embedded", r.stdout)     # warns about embedded defs

    def test_lock_missing_hip_is_actionable(self):
        r = self.sb.mfx("lock", str(self.sb.home / "nope.hip"),
                        env_extra={"MFX_HYTHON": "/bin/true"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not exist", r.stderr)

    def test_lock_no_houdini_is_actionable(self):
        hip = self.sb.home / "s.hip"
        hip.write_bytes(b"x")
        # empty dir instead of /Applications/Houdini
        r = self.sb.mfx("lock", str(hip), "--hfs",
                        str(self.sb.home / "fakehfs"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("hython", r.stderr)


if __name__ == "__main__":
    unittest.main()
