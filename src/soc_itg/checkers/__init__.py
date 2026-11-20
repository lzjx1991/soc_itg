from .connectivity import run_checks as _connectivity_checks
from .width import check_width


def run_checks(soc):
    return _connectivity_checks(soc) + check_width(soc)

