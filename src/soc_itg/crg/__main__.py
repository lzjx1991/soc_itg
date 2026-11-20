import argparse
import sys

from . import __version__
from .generate import generate
from .parser import CrgError, parse
from .validate import validate


def cmd_validate(args):
    m = parse(args.input)
    errs, warns, clk_order, rst_order = validate(m)
    for w in warns:
        print("WARN :", w)
    if errs:
        raise CrgError(errs)
    print(f"OK: module '{m.module}' v{m.version}: "
          f"{len(m.clocks)} clock nodes, {len(m.resets)} reset nodes, "
          f"{len(m.regs)} registers")


def cmd_gen(args):
    generate(args.input, args.out, gen_tb=not args.no_tb)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="crg_gen",
        description="Table-driven CRG (clock/reset generation) RTL generator")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen", help="generate RTL/regs/TB from a spec")
    g.add_argument("-i", "--input", required=True,
                   help=".xlsx file or directory of csv sheets")
    g.add_argument("-o", "--out", required=True, help="output directory")
    g.add_argument("--no-tb", action="store_true", help="skip testbench output")
    g.set_defaults(func=cmd_gen)

    v = sub.add_parser("validate", help="validate a spec only")
    v.add_argument("-i", "--input", required=True)
    v.set_defaults(func=cmd_validate)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except CrgError as e:
        print("ERROR: specification has problems:", file=sys.stderr)
        for msg in e.msgs:
            print("  -", msg, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
