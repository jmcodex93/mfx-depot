import json, unittest
from util import Sandbox, SandboxCase
import fixtures


class TestDoctor(SandboxCase, unittest.TestCase):
    def test_clean_install_reports_no_problems(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("No problems found", r.stdout)

    def test_duplicate_hda_definitions_error(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        self.sb.mfx("install", str(z), "--name", "Copy Two", "--yes")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("mfx::camrig::2.0", r.stdout)
        self.assertIn("keep one", r.stdout)

    def test_shelf_collision_warns(self):
        t1 = fixtures.make_labs_tree(self.sb.home / "a")
        self.sb.mfx("install", str(t1), "--yes")
        t2 = fixtures.make_labs_tree(self.sb.home / "b")
        self.sb.mfx("install", str(t2), "--name", "Labs Clone", "--yes")
        r = self.sb.mfx("doctor")
        self.assertIn("labs_tool", r.stdout)
        self.assertIn("TAB", r.stdout)

    def test_broken_package_file_error(self):
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "broken.json").write_text("{nope")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("broken.json", r.stdout)
        self.assertIn("fix the JSON or delete", r.stdout)

    def test_dangling_foreign_env_path_error(self):
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "Ghost.json").write_text(json.dumps(
            {"env": [{"GHOST": str(self.sb.home / "nope")}],
             "path": "$GHOST"}))
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not exist", r.stdout)

    def test_lax_package_json_is_not_broken(self):
        # Real-world MOPS_Plus.json / Modeler.json: Houdini tolerates
        # // comments and trailing commas, so doctor must too.
        tree = self.sb.home / "MOPS"
        (tree / "otls").mkdir(parents=True)
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "MOPS_Plus.json").write_text(
            '{\n'
            '  // MOPS plus license package\n'
            '  "env": [\n'
            '    {"MOPS": "%s"},\n'
            '  ],\n'
            '  "path": "$MOPS",\n'
            '}\n' % tree)
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertNotIn("broken", r.stdout)

    def test_still_broken_after_lax_parse_errors(self):
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "really_broken.json").write_text('{"env": [}')
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("really_broken.json", r.stdout)

    def test_duplicate_hda_across_prefs_majors_is_not_conflict(self):
        # 21.0 only loads its own prefs, 22.0 its own: no clash.
        for prefs in (self.sb.prefs21, self.sb.prefs22):
            fixtures.make_dummy_hda(prefs / "otls" / "tool.hda",
                                    table="Sop", optype="user::tool::1.0")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertNotIn("keep one", r.stdout)

    def test_user_otls_duplicate_of_managed_package_conflicts(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        fixtures.make_dummy_hda(self.sb.prefs21 / "otls" / "dup.hda",
                                table="Object", optype="mfx::camrig::2.0")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("keep one", r.stdout)

    def test_duplicate_within_same_prefs_conflicts(self):
        tree = fixtures.make_labs_tree(self.sb.home / "labs")
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "Labs.json").write_text(json.dumps(
            {"env": [{"LABS": str(tree)}], "path": "$LABS"}))
        fixtures.make_dummy_hda(self.sb.prefs21 / "otls" / "dup.hda",
                                table="Sop", optype="labs::tool::1.0")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("keep one", r.stdout)

    def test_env_path_list_with_default_token_ok(self):
        lib = self.sb.home / "hqlib"
        lib.mkdir()
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "Lib.json").write_text(json.dumps(
            {"env": [{"HOUDINI_OTLSCAN_PATH": "%s;&" % lib}]}))
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertNotIn("does not exist", r.stdout)

    def test_env_path_list_missing_token_errors(self):
        lib = self.sb.home / "hqlib"
        lib.mkdir()
        missing = self.sb.home / "nope"
        pkg = self.sb.prefs21 / "packages"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "Lib.json").write_text(json.dumps(
            {"env": [{"HOUDINI_OTLSCAN_PATH": "%s;%s" % (lib, missing)}]}))
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not exist", r.stdout)
        self.assertIn(str(missing), r.stdout)

    def test_missing_payload_error(self):
        z = fixtures.make_camrig_zip(self.sb.home)
        self.sb.mfx("install", str(z), "--yes")
        import shutil
        shutil.rmtree(self.sb.home / "MFX" / "camrig")
        r = self.sb.mfx("doctor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("mfx repair", r.stdout)


if __name__ == "__main__":
    unittest.main()
