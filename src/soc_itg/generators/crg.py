import json
from pathlib import Path

from ..crg.parser import parse
from ..crg.generate import generate


def _specs(crg_dir):
    specs = []
    if not crg_dir.exists():
        return specs
    specs += sorted(crg_dir.glob("*.xlsx"))
    specs += [d for d in sorted(crg_dir.iterdir()) if d.is_dir() and any(d.glob("*.csv"))]
    return specs


def _copy_tree(src, dst):
    for f in src.rglob("*"):
        if f.is_file():
            target = dst / f.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f.read_bytes())


def process_crg(repo_root, gen_tb=False):
    repo = Path(repo_root)
    crg_dir = repo / "crg"
    out_root = repo / "generated" / "crg"
    rtl_out = repo / "generated" / "rtl"
    sdc_out = repo / "generated" / "sdc"
    out_root.mkdir(parents=True, exist_ok=True)
    rtl_out.mkdir(parents=True, exist_ok=True)
    sdc_out.mkdir(parents=True, exist_ok=True)

    modules = []
    for spec in _specs(crg_dir):
        model = parse(str(spec))
        module = model.module
        target = out_root / module
        generate(str(spec), str(target), gen_tb=gen_tb)
        if (target / "rtl").exists():
            _copy_tree(target / "rtl", rtl_out)
        for sdc in target.glob("*.sdc"):
            sdc_out.mkdir(parents=True, exist_ok=True)
            (sdc_out / sdc.name).write_bytes(sdc.read_bytes())
        modules.append({"module": module, "spec": str(spec), "out": str(target)})

    build = repo / "build"
    build.mkdir(parents=True, exist_ok=True)
    (build / "crg.json").write_text(json.dumps({"schema_version": 1, "crg": modules}, indent=2), encoding="utf-8")
    return modules
