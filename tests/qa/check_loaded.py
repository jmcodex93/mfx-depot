"""Assert the installed package actually loads, and that hda_index
agrees with Houdini about its operator types."""
import sys
from pathlib import Path

import hou

t = hou.nodeType(hou.sopNodeTypeCategory(), "mfx::qafixture::1.0")
assert t is not None, "package did not load: mfx::qafixture::1.0 missing"
lib = t.definition().libraryFilePath()

sys.path.insert(0, "src")
from mfx.hda_index import operator_types            # noqa: E402
ops = operator_types(Path(lib))
assert ("Sop", "mfx::qafixture::1.0") in ops, \
    "hda_index disagrees with hou.hda: %r" % (ops,)
print("load + hda_index cross-check OK (%s)" % lib)
