"""Extract operator type names from .hda/.otl files WITHOUT Houdini.

Two on-disk index conventions are scanned for, since real HDAs use either:

1. Old-style ASCII/expanded text index: line-oriented blocks with
   'Operator:' and 'Table:' lines (e.g. what hotl -X produces, and what
   tests/fixtures.make_dummy_hda writes for the synthetic test fixtures).

2. Modern binary-format .hda (the default since current Houdini): there
   is no literal 'Operator:'/'Table:' text anywhere. Instead the INDX
   section index embeds each operator definition under a key of the form
   '[namespace::]Table/name[::version]', e.g. 'mfx::Sop/vibrate::1.0' for
   operator type 'mfx::vibrate::1.0' in the Sop table. This was confirmed
   by copying a real production HDA
   (~/Library/Preferences/houdini/22.0/otls/mfx_vibrate_1.0.hda) into
   tests/fixtures/ and inspecting its bytes: it contains no 'Operator:'
   or 'Table:' strings at all, only this slash-keyed section name.

We scan the raw bytes (latin-1) for both patterns rather than parsing
either container format. Tier-2 QA (Task 16) cross-checks against
hou.hda.
"""
import re
from pathlib import Path

from .errors import DepotError

# --- old-style ASCII/expanded text index ---
OP_RE = re.compile(r"^Operator:[ \t]*(\S+)[ \t]*$", re.M)
TABLE_RE = re.compile(r"^Table:[ \t]*(\S+)[ \t]*$", re.M)
BLOCK_SPAN = 2000       # a table line lives near its operator line

# --- modern binary-format section-index key ---
# Houdini's operator tables; used to anchor the slash-key pattern so it
# doesn't match unrelated slash-separated text (URLs, file paths, ...).
_TABLES = ("Object", "Sop", "Pop", "Dop", "Chop", "Chopnet", "Cop2",
           "CopNet", "Vop", "Vopnet", "Shop", "Driver", "TopNet", "Lop")
# A leading negative lookbehind for [A-Za-z0-9_] stops a match from
# starting mid-identifier (e.g. the "Sop" inside "randomStopSop/xyz" or
# the "Shop" inside "FooBarShop/thing" must NOT match -- only a table
# name at a genuine identifier boundary counts). It is satisfied
# trivially at offset 0 and after any non-word byte, which is exactly
# where real section keys sit in the binary format. The trailing
# optype capture ([A-Za-z0-9_.:]+) is greedy over that character class
# and simply stops at the first byte outside it -- tier-2 QA (Task 16)
# cross-checks the result against hou.hda.
KEY_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:([A-Za-z_][\w.]*)::)?(%s)/([A-Za-z0-9_.:]+)"
    % "|".join(_TABLES))


def _scan_text_blocks(text):
    out = []
    for m in OP_RE.finditer(text):
        t = TABLE_RE.search(text, m.end(), m.end() + BLOCK_SPAN)
        if t:
            out.append((t.group(1), m.group(1)))
    return out


def _scan_binary_keys(text):
    out = []
    for m in KEY_RE.finditer(text):
        namespace, table, rest = m.group(1), m.group(2), m.group(3)
        optype = "%s::%s" % (namespace, rest) if namespace else rest
        out.append((table, optype))
    return out


def operator_types(path):
    path = Path(path)
    try:
        text = path.read_bytes().decode("latin-1")
    except OSError as e:
        raise DepotError("cannot read %s (%s)" % (path, e))
    seen, out = set(), []
    for pair in _scan_text_blocks(text) + _scan_binary_keys(text):
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    if not out:
        raise DepotError(
            "no operator index found in %s -- unreadable or not an HDA "
            "library. 'mfx doctor' will list it as unreadable." % path)
    return out
