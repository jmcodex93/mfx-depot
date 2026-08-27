"""Build a real .hda fixture: a SOP subnet published as mfx::qafixture::1.0."""
import sys
from pathlib import Path

import hou

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
geo = hou.node("/obj").createNode("geo")
sub = geo.createNode("subnet")
sub.createDigitalAsset(name="mfx::qafixture::1.0",
                       hda_file_name=str(out), min_num_inputs=0)
print("built %s" % out)
