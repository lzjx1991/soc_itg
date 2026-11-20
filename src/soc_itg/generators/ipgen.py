from pathlib import Path

from ..model import Component, FileSet, FileItem
from ..topcsr.excel import read_topcsr
from ..ipxact.writer import write_component_file


def build_component(name, vlnv, regs_path, rtl_files=None):
    topcsr = read_topcsr(str(regs_path), module=name)
    files = [FileItem(name=f, file_type="verilogSource") for f in (rtl_files or [])]
    file_sets = [FileSet(name="rtl", files=files)] if files else []
    return Component(vlnv=vlnv, memory_maps=[topcsr.memory_map], file_sets=file_sets)


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
    component = build_component(name, vlnv, Path(regs), rtl_files)
    out = repo.ipxact_dir / f"{name}.xml"
    write_component_file(component, out)
    return out
