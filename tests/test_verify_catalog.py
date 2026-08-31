import json, subprocess, unittest
from util import REPO, Sandbox, SandboxCase
import fixtures


class TestVerifyCatalog(SandboxCase, unittest.TestCase):
    def _run(self, cat_obj):
        f = self.sb.home / "cat.json"
        f.write_text(json.dumps(cat_obj))
        return subprocess.run(["zsh", str(REPO / "bin" / "verify-catalog"),
                               str(f)], capture_output=True, text=True,
                              cwd=str(REPO), env=self.sb.env())

    def test_offline_catalog_passes(self):
        z = fixtures.make_camrig_zip(self.sb.home)   # file:// source = offline
        r = self._run({"schema": 1, "packages": [
            {"slug": "camrig", "name": "MFX CamRig", "type": "free",
             "source": z.resolve().as_uri()},
            {"slug": "modeler", "type": "commercial",
             "buy_url": "https://x"}]})              # commercial skipped
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS  camrig", r.stdout)
        self.assertNotIn("modeler", r.stdout)

    def test_broken_source_fails(self):
        r = self._run({"schema": 1, "packages": [
            {"slug": "ghost", "name": "Ghost", "type": "free",
             "source": "file:///nonexistent/ghost.zip"}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  ghost", r.stdout)

    def test_malformed_catalog_fails(self):
        f = self.sb.home / "cat.json"
        f.write_text("{nope")  # Invalid JSON
        r = subprocess.run(["zsh", str(REPO / "bin" / "verify-catalog"),
                           str(f)], capture_output=True, text=True,
                          cwd=str(REPO), env=self.sb.env())
        self.assertEqual(r.returncode, 1)
        self.assertIn("could not parse", r.stderr)

    def test_shipped_catalog_is_valid_schema(self):
        data = json.loads((REPO / "catalog.json").read_text())
        self.assertEqual(data["schema"], 1)
        slugs = []
        for e in data["packages"]:
            self.assertIn("slug", e)
            slugs.append(e["slug"])
            self.assertIn(e["type"], ("free", "commercial"))
            if e["type"] == "free":
                self.assertIn("source", e)
            else:
                self.assertIn("buy_url", e)
        # Spec §5.1: slugs are unique
        self.assertEqual(len(slugs), len(set(slugs)),
                        "Duplicate slugs found in catalog")


if __name__ == "__main__":
    unittest.main()
