import argparse
import json
import shutil
import sys
from pathlib import Path

from .. import __version__, SCHEMA_VERSION
from ..ipxact import read_component
from ..assemble import assemble
from ..checkers import run_checks
from ..model import SoC, MemoryMap
from ..generators.top_rtl import generate_top_rtl
from ..generators.csr import generate_csr_header
from ..workspace import find_workspace, load_workspace, current_repo, load_repo
from ..generators.filelist import generate_filelists
from ..create import create_project
from ..pinmux import read_pinmux, validate as validate_pinmux
from ..pinmux.model import Pinmux as PinmuxModel
from ..pinmux.registers import build_registers
from ..generators.regblock import generate_regblock
from ..generators.pinmux import generate_pinmux
from ..generators.crg import process_crg
from ..generators.netlist_emit import emit_netlist
from ..connectivity import build_netlist
from ..model.netlist import Netlist
from ..model.topcsr import TopCSR
from ..topcsr import read_topcsr


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


def _build_connectivity(paths):
    soc = SoC.model_validate_json(paths["soc"].read_text(encoding="utf-8"))
    pm_path = paths["root"] / "build" / "pinmux.json"
    pinmux = PinmuxModel.model_validate_json(pm_path.read_text(encoding="utf-8")) if pm_path.exists() else None
    tc_path = paths["root"] / "build" / "topcsr.json"
    topcsr = TopCSR.model_validate_json(tc_path.read_text(encoding="utf-8")) if tc_path.exists() else None
    netlist = build_netlist(soc, pinmux, topcsr, tool_version=__version__)
    out = paths["root"] / "build" / "connectivity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(netlist.model_dump_json(indent=2), encoding="utf-8")
    return netlist


def cmd_connect(args):
    paths = _paths(args.project)
    netlist = _build_connectivity(paths)
    print(f"[connect] ports={len(netlist.ports)} instances={len(netlist.instances)} nets={len(netlist.nets)} -> {paths['root'] / 'build' / 'connectivity.json'}")
    return 0


def cmd_parse(args):
    paths = _paths(args.project)
    components = {}
    files = []
    search = []
    if paths["ip"].exists():
        search.append(paths["ip"])
    local_ipxact = paths["root"] / "ipxact"
    if local_ipxact.exists():
        search.append(local_ipxact)
    ws_root = find_workspace(paths["root"])
    if ws_root is not None:
        ws = load_workspace(ws_root)
        for repo in ws.repos.values():
            if repo.ipxact_dir.exists():
                search.append(repo.ipxact_dir)
    for directory in search:
        files.extend(sorted(directory.rglob("*.xml")))
    files = sorted(set(files))
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
        tc_path = paths["root"] / "build" / "topcsr.json"
        if tc_path.exists():
            topcsr = TopCSR.model_validate_json(tc_path.read_text(encoding="utf-8"))
            if topcsr.memory_map.registers:
                target = rtl / f"{soc.top}_top_regs.v"
                target.write_text(generate_regblock(f"{soc.top}_top_regs", topcsr.memory_map), encoding="utf-8")
                made.append(target)
    if gen in ("top", "all"):
        nl_path = paths["root"] / "build" / "connectivity.json"
        if not nl_path.exists():
            _build_connectivity(paths)
        netlist = Netlist.model_validate_json(nl_path.read_text(encoding="utf-8"))
        target = rtl / f"{soc.top}.v"
        target.write_text(emit_netlist(netlist), encoding="utf-8")
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
    if gen in ("sdc", "all"):
        from ..generators.sdc import merge_sdc
        made.append(merge_sdc(load_repo(paths["root"])))
    if gen in ("ral", "all"):
        from ..generators.ral import generate_ral
        d = generated / "ral"
        d.mkdir(parents=True, exist_ok=True)
        target = d / f"{soc.top}_ral.sv"
        target.write_text(generate_ral(soc), encoding="utf-8")
        made.append(target)
    if gen in ("docs", "all"):
        from ..generators.regdoc import generate_regdoc
        d = generated / "docs"
        d.mkdir(parents=True, exist_ok=True)
        target = d / f"{soc.top}_regmap.md"
        target.write_text(generate_regdoc(soc), encoding="utf-8")
        made.append(target)
    for m in made:
        print(f"[generate] -> {m}")
    return 0


def cmd_flow(args):
    paths = _paths(args.project)
    repo = load_repo(paths["root"])
    from ..flow import plan_flow, flow_command
    tops = set(args.top.split(",")) if getattr(args, "top", None) else None
    plans = plan_flow(repo, args.tool, tops)
    if not plans:
        print(f"[flow] no tasks for {args.tool}")
        return 0
    for task in plans:
        print(f"[flow] (dry-run) {flow_command(args.tool, task)}")
    return 0


def cmd_open(args):
    tool = getattr(args, "command", "")
    print(f"[{tool}] (dry-run) {tool} --top {' '.join(args.top or [])}")
    return 0


def cmd_itg(args):
    from ..integrate import plan_integration
    paths = _paths(args.project)
    ws, repo, repos = plan_integration(paths["root"])
    stages = [cmd_parse, cmd_assemble, cmd_pinmux, cmd_topcsr, cmd_crg, cmd_check, cmd_connect, cmd_generate, cmd_filelist]
    original = args.project
    for target in repos:
        print(f"[itg] integrate '{target.name}'")
        args.project = str(target.path)
        for step in stages:
            try:
                step(args)
            except Exception as exc:
                print(f"[itg] skip {step.__name__}@{target.name}: {exc}")
    args.project = original
    return 0


def cmd_ipgen(args):
    paths = _paths(args.project)
    repo = load_repo(paths["root"])
    from ..generators.ipgen import ipgen
    out = ipgen(repo, name=args.top, regs=args.regs, vlnv=args.vlnv)
    print(f"[ipgen] -> {out}")
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


def cmd_topcsr(args):
    paths = _paths(args.project)
    xlsx = Path(args.file) if getattr(args, "file", None) else paths["root"] / "top_csr.xlsx"
    soc = SoC.model_validate_json(paths["soc"].read_text(encoding="utf-8"))
    topcsr = read_topcsr(str(xlsx), module=f"{soc.top}_top_regs")
    out = paths["root"] / "build" / "topcsr.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(topcsr.model_dump_json(indent=2), encoding="utf-8")
    print(f"[topcsr] regs={len(topcsr.memory_map.registers)} bindings={len(topcsr.bindings)} -> {out}")
    return 0


def cmd_crg(args):
    paths = _paths(args.project)
    modules = process_crg(paths["root"], gen_tb=getattr(args, "tb", False))
    for m in modules:
        print(f"[crg] {m['module']} <- {m['spec']}")
    print(f"[crg] {len(modules)} module(s) -> {paths['root'] / 'generated' / 'crg'}")
    return 0


def cmd_filelist(args):
    paths = _paths(args.project)
    repo = load_repo(paths["root"])
    top = None
    if paths["soc"].exists():
        top = SoC.model_validate_json(paths["soc"].read_text(encoding="utf-8")).top
    elif repo.soc:
        top = (repo.soc.get("design", {}) or {}).get("name")
    result = generate_filelists(repo, top_name=top)
    print(f"[filelist] {len(result['files'])} file(s) -> {result['outdir']}")
    return 0


def cmd_status(args):
    root = Path(args.project).resolve()
    ws_root = find_workspace(root)
    if ws_root is not None:
        ws = load_workspace(ws_root)
        repo = current_repo(ws, root)
        print(f"workspace : {ws.name} ({ws_root})")
        print(f"default_top: {ws.default_top}")
        print(f"repos     : {len(ws.repos)}")
        if repo is not None:
            print(f"current   : {repo.name}")
    else:
        repo = load_repo(root)
        print(f"repo      : {repo.name} ({root})")
        print("workspace : (no workspace.yaml, single-repo mode)")
    return 0


def cmd_repos(args):
    ws_root = find_workspace(Path(args.project).resolve())
    if ws_root is None:
        print("no workspace.yaml")
        return 0
    ws = load_workspace(ws_root)
    for name, repo in ws.repos.items():
        print(f"{name}\t{repo.vlnv or ''}")
    return 0


def cmd_tops(args):
    root = Path(args.project).resolve()
    ws_root = find_workspace(root)
    if ws_root is not None:
        ws = load_workspace(ws_root)
        if ws.default_top:
            print(ws.default_top)
        for repo in ws.repos.values():
            design = (repo.soc or {}).get("design", {}) or {}
            if design.get("name"):
                print(design["name"])
    else:
        repo = load_repo(root)
        design = (repo.soc or {}).get("design", {}) or {}
        if design.get("name"):
            print(design["name"])
    return 0


def cmd_clean(args):
    paths = _paths(args.project)
    build = paths["root"] / "build"
    if build.exists():
        shutil.rmtree(build)
        print("[clean] removed build/")
    return 0


def cmd_create(args):
    messages = create_project(args.prj, sub=args.sub, init=args.init, no_git=args.no_git)
    for message in messages:
        print(f"[create] {message}")
    return 0


def cmd_hier(args):
    paths = _paths(args.project)
    repo = load_repo(paths["root"])
    design = (repo.soc or {}).get("design", {}) or {}
    instances = [dict(i) for i in design.get("instances", [])]
    connections = list(design.get("connections", []))
    from ..ipxact.resolve import repo_components
    try:
        comps = repo_components(repo)
    except Exception:
        comps = {}
    for spec in instances:
        if "module" in spec:
            continue
        comp = comps.get(spec.get("vlnv"))
        if comp is not None:
            spec["module"] = comp.vlnv.split(":")[2]
            spec["ports"] = [{"name": p.name, "direction": p.direction, "width": p.width} for p in comp.ports]
        else:
            spec["module"] = spec["name"]
    from ..hierarchical import build_hierarchy, emit_hierarchy
    modules, top = build_hierarchy(instances, connections, top_name=design.get("name"))
    texts = emit_hierarchy(modules)
    outdir = paths["root"] / "generated" / "rtl"
    outdir.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        target = outdir / f"{name}_hier.v"
        target.write_text(text, encoding="utf-8")
        print(f"[hier] -> {target}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="soc-itg")
    parser.add_argument("-C", "--project", default=".", help="project directory")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("parse")
    sub.add_parser("assemble")
    sub.add_parser("check")
    sub.add_parser("connect")

    gen = sub.add_parser("generate")
    gen.add_argument("-g", "--gen", default="all", choices=["all", "top", "csr", "pinmux", "sdc", "ral", "docs"])

    build = sub.add_parser("build")
    build.add_argument("-g", "--gen", default="all", choices=["all", "top", "csr", "pinmux", "sdc", "ral", "docs"])
    build.add_argument("--fail-on-error", action="store_true")

    pinmux = sub.add_parser("pinmux")
    pinmux.add_argument("file", nargs="?")

    topcsr = sub.add_parser("topcsr")
    topcsr.add_argument("file", nargs="?")

    crg = sub.add_parser("crg")
    crg.add_argument("--tb", action="store_true")

    sub.add_parser("status")
    sub.add_parser("repos")
    sub.add_parser("tops")
    sub.add_parser("filelist")
    sub.add_parser("clean")

    create = sub.add_parser("create")
    create.add_argument("--prj", required=True)
    create.add_argument("--sub")
    create.add_argument("--init", action="store_true")
    create.add_argument("--no-git", action="store_true")

    itg = sub.add_parser("itg")
    itg.add_argument("--top")

    ipgen = sub.add_parser("ipgen")
    ipgen.add_argument("--top")
    ipgen.add_argument("--regs")
    ipgen.add_argument("--vlnv")

    flow = sub.add_parser("flow")
    flow.add_argument("tool")
    flow.add_argument("--top")

    verdi = sub.add_parser("verdi")
    verdi.add_argument("--top", nargs="*")

    vcs = sub.add_parser("vcs")
    vcs.add_argument("--top", nargs="*")

    sub.add_parser("hier")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "parse": cmd_parse,
        "assemble": cmd_assemble,
        "check": cmd_check,
        "connect": cmd_connect,
        "generate": cmd_generate,
        "build": cmd_build,
        "pinmux": cmd_pinmux,
        "topcsr": cmd_topcsr,
        "crg": cmd_crg,
        "status": cmd_status,
        "repos": cmd_repos,
        "tops": cmd_tops,
        "filelist": cmd_filelist,
        "clean": cmd_clean,
        "create": cmd_create,
        "itg": cmd_itg,
        "ipgen": cmd_ipgen,
        "flow": cmd_flow,
        "verdi": cmd_open,
        "vcs": cmd_open,
        "hier": cmd_hier,
    }
    if args.command is None:
        parser.print_help()
        return 0
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
