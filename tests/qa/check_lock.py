"""Validate the lockfile produced against the QA scene."""
import json
import sys

lock = json.loads(open(sys.argv[1]).read())
pkgs = {p["slug"]: p for p in lock["packages"]}
assert "qa-fixture" in pkgs, "lockfile missed the package: %r" % lock
assert pkgs["qa-fixture"]["version"] == "1.0", lock
assert any("qafixture" in t for t in pkgs["qa-fixture"]["types"]), lock
print("lockfile OK")
