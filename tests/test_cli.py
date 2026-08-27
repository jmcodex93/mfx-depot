import unittest
from util import Sandbox, SandboxCase


class TestEntry(SandboxCase, unittest.TestCase):
    def test_version_flag(self):
        r = self.sb.mfx("--version")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.strip(), r"^mfx \d+\.\d+\.\d+$")

    def test_no_args_prints_usage_and_fails(self):
        r = self.sb.mfx()
        self.assertEqual(r.returncode, 1)
        self.assertIn("usage", (r.stdout + r.stderr).lower())

    def test_unknown_command_fails(self):
        r = self.sb.mfx("frobnicate")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
