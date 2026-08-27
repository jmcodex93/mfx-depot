"""Save a hip that instances the fixture HDA."""
import sys

import hou

geo = hou.node("/obj").createNode("geo")
geo.createNode("mfx::qafixture::1.0")
hou.hipFile.save(sys.argv[1])
print("saved %s" % sys.argv[1])
