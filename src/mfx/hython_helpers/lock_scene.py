"""Runs INSIDE hython: open a hip, list HDA-defined node types.
Prints one JSON line to stdout; everything else goes to stderr."""
import json
import sys

import hou


def main():
    hip = sys.argv[1]
    hou.hipFile.load(hip, suppress_save_prompt=True,
                     ignore_load_warnings=True)
    records = []
    for node in hou.node("/").allSubChildren():
        d = node.type().definition()
        if d is None:
            continue
        records.append({"type": node.type().nameWithCategory(),
                        "library": d.libraryFilePath()})
    print(json.dumps({"houdini": hou.applicationVersionString(),
                      "records": records}))


if __name__ == "__main__":
    main()
