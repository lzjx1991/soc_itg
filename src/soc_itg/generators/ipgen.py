from pathlib import Path

from ..model import Component, FileSet, FileItem, Port
from ..topcsr.excel import read_topcsr
from ..ipxact.writer import write_component_file
from .rtl_ports import extract_ports


def build_component(name, vlnv, regs_path, rtl_files=None, ports=None):
    topcsr = read_topcsr(str(regs_path), module=name)
    files = [FileItem(name=f, file_type="verilogSource") for f in (rtl_files or [])]
    file_sets = [FileSet(name="rtl", files=files)] if files else []
    return Component(vlnv=vlnv, ports=ports or [], memory_maps=[topcsr.memory_map], file_sets=file_sets)


def _rtl_ports(repo):
    mapping = {"input": "in", "output": "out", "inout": "inout"}
    if not repo.rtl_dir.exists():
        return []
    for f in sorted(repo.rtl_dir.rglob("*")):
        if f.suffix in (".v", ".sv"):
            _, ports = extract_ports(f.read_text(encoding="utf-8", errors="ignore"))
            if ports:
                return [Port(name=p["name"], direction=mapping.get(p["direction"], "in"), width=p["width"]) for p in ports]
    return []


def ipgen(repo, name=None, regs=None, vlnv=None):
    name = name or repo.name
    vlnv = vlnv or repo.vlnv or f"local:Local:{name}:0.1.0"
    if regs is None:
        candidates = sorted(repo.csr_dir.glob("*.xlsx")) if repo.csr_dir.exists() else []
        regs = candidates[0] if candidates else None
    if regs is None:
        raise FileNotFoundError("no register excel found under csr/*.xlsx")
    rtl_files = []
    if repo.rtl_dir.exists():
        rtl_files = sorted(str(p.relative_to(repo.path)) for p in repo.rtl_dir.rglob("*") if p.suffix in (".v", ".sv"))
    component = build_component(name, vlnv, Path(regs), rtl_files, ports=_rtl_ports(repo))
    out = repo.ipxact_dir / f"{name}.xml"
    write_component_file(component, out)
    return out
