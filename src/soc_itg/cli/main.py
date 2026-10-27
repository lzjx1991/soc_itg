import argparse
import json
import sys
from pathlib import Path

from .. import __version__, SCHEMA_VERSION
from ..ipxact import read_component
from ..assemble import assemble
from ..checkers import run_checks
from ..model import SoC, MemoryMap
from ..generators.top_rtl import generate_top_rtl
from ..generators.csr import generate_csr_header
from ..pinmux import read_pinmux, validate as validate_pinmux
from ..pinmux.model import Pinmux as PinmuxModel
from ..pinmux.registers import build_registers
from ..generators.regblock import generate_regblock
from ..generators.pinmux import generate_pinmux


def _paths(project):
    root = Path(project).resolve()
    return {
        "root": root,
        "ip": root / "ip",
        "ipdb": root / "build" / "ipdb.json",
        "soc_yaml": root / "soc.yaml",
        "soc": root / "build" / "soc.json",
        "findings": root / "build" / "findings.json",
        "generated": root / "generated",
    }


def _san(name):
    return "".join(c.lower() if c.isalnum() else "_" for c in name)


def _merge_memory_maps(mem_maps):
    registers = []
    for mm in mem_maps:
        registers.extend(mm.registers)
    return MemoryMap(name="merged", registers=registers)


def cmd_parse(args):
    paths = _paths(args.project)
    components = {}
    files = sorted(paths["ip"].glob("*.xml"))
    for f in files:
        comp = read_component(f)
        components[comp.vlnv] = json.loads(comp.model_dump_json())
    paths["ipdb"].parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION, "tool_version": __version__, "components": components}
    paths["ipdb"].write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[parse] {len(files)} IP-XACT file(s) -> {paths['ipdb']}")
    return 0


def cmd_assemble(args):
    paths = _paths(args.project)
    assemble(str(paths["ipdb"]), str(paths["soc_yaml"]), str(paths["soc"]))
    print(f"[assemble] -> {paths['soc']}")
    return 0


def cmd_check(args):
    paths = _paths(args.project)
    soc = SoC.model_validate_json(paths["soc"].read_text(encoding="utf-8"))
    findings = run_checks(soc)
    paths["findings"].parent.mkdir(parents=True, exist_ok=True)
    paths["findings"].write_text(json.dumps({"schema_version": SCHEMA_VERSION, "findings": findings}, indent=2), encoding="utf-8")
    for f in findings:
        print(f"  [{f['level']}] {f['code']}: {f['msg']}")
    errors = [f for f in findings if f["level"] == "error"]
    print(f"[check] {len(findings)} finding(s), {len(errors)} error(s)")
    return 1 if errors else 0


def cmd_generate(args):
    paths = _paths(args.project)
    soc = SoC.model_validate_json(paths["soc"].read_text(encoding="utf-8"))
    gen = getattr(args, "gen", "all") or "all"
    generated = paths["generated"]
    rtl = generated / "rtl"
    rtl.mkdir(parents=True, exist_ok=True)
    made = []
    if gen in ("csr", "all"):
        csr_dir = generated / "csr"
        csr_dir.mkdir(parents=True, exist_ok=True)
        header = csr_dir / f"{soc.top}_csr.h"
        header.write_text(generate_csr_header(soc), encoding="utf-8")
        made.append(header)
        for inst in soc.instances:
            mem_maps = soc.register_models.get(inst.name) or []
            if not mem_maps:
                continue
            merged = _merge_memory_maps(mem_maps)
            if not merged.registers:
                continue
            target = rtl / f"{_san(inst.name)}_regs.v"
            target.write_text(generate_regblock(f"{_san(inst.name)}_regs", merged), encoding="utf-8")
            made.append(target)
    if gen in ("top", "all"):
        target = rtl / f"{soc.top}.v"
        target.write_text(generate_top_rtl(soc), encoding="utf-8")
        made.append(target)
    if gen in ("pinmux", "all"):
        pm_path = paths["root"] / "build" / "pinmux.json"
        if pm_path.exists():
            pm = PinmuxModel.model_validate_json(pm_path.read_text(encoding="utf-8"))
            reg_map, cfg_meta = build_registers(pm)
            reg_target = rtl / f"{soc.top}_pinmux_regs.v"
            reg_target.write_text(generate_regblock(f"{soc.top}_pinmux_regs", reg_map), encoding="utf-8")
            made.append(reg_target)
            pm_target = rtl / f"{soc.top}_pinmux.v"
            pm_target.write_text(generate_pinmux(soc, pm, reg_map, cfg_meta), encoding="utf-8")
            made.append(pm_target)
        else:
            print("[generate] skip pinmux: build/pinmux.json not found (run 'soc-itg pinmux' first)")
    for m in made:
        print(f"[generate] -> {m}")
    return 0


def cmd_build(args):
    rc = cmd_parse(args)
    if rc:
        return rc
    rc = cmd_assemble(args)
    if rc:
        return rc
    rc = cmd_check(args)
    if rc and getattr(args, "fail_on_error", False):
        return rc
    return cmd_generate(args)


def cmd_pinmux(args):
    paths = _paths(args.project)
    xlsx = Path(args.file) if getattr(args, "file", None) else paths["root"] / "pinmux.xlsx"
    pinmux = read_pinmux(str(xlsx))
    findings = validate_pinmux(pinmux)
    out = paths["root"] / "build" / "pinmux.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pinmux.model_dump_json(indent=2), encoding="utf-8")
    for f in findings:
        print(f"  [{f['level']}] {f['code']}: {f['msg']}")
    errors = [f for f in findings if f["level"] == "error"]
    print(f"[pinmux] pads={len(pinmux.pads)} function={len(pinmux.function_share)} padshare={len(pinmux.padshare)} bist={len(pinmux.bist_share)} -> {out}")
    print(f"[pinmux] {len(findings)} finding(s), {len(errors)} error(s)")
    return 1 if errors else 0


def build_parser():
    parser = argparse.ArgumentParser(prog="soc-itg")
    parser.add_argument("-C", "--project", default=".", help="project directory")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("parse")
    sub.add_parser("assemble")
    sub.add_parser("check")

    gen = sub.add_parser("generate")
    gen.add_argument("-g", "--gen", default="all", choices=["all", "top", "csr", "pinmux"])

    build = sub.add_parser("build")
    build.add_argument("-g", "--gen", default="all", choices=["all", "top", "csr", "pinmux"])
    build.add_argument("--fail-on-error", action="store_true")

    pinmux = sub.add_parser("pinmux")
    pinmux.add_argument("file", nargs="?")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "parse": cmd_parse,
        "assemble": cmd_assemble,
        "check": cmd_check,
        "generate": cmd_generate,
        "build": cmd_build,
        "pinmux": cmd_pinmux,
    }
    if args.command is None:
        parser.print_help()
        return 0
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
