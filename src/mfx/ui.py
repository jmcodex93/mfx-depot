import sys
from .errors import DepotError


def confirm(question, assume_yes):
    if assume_yes:
        return True
    try:
        return input("%s [y/N] " % question).strip().lower() in ("y", "yes")
    except EOFError:
        raise DepotError("cannot ask for confirmation in this terminal; "
                         "re-run with --yes")


def out(msg=""):
    sys.stdout.write(msg + "\n")
