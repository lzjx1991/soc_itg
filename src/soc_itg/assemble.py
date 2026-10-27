import json
from pathlib import Path
from .model import SoC
from .design.loader import load_soc_yaml


def _load_ipdb(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assemble(ipdb_path, soc_yaml_path, out_path):
    ipdb = _load_ipdb(ipdb_path)
    components = ipdb.get("components", {})
    top, instances, connections, address_map = load_soc_yaml(soc_yaml_path)
    used = {}
    register_models = {}
    for inst in instances:
        if inst.vlnv not in components:
            raise KeyError(f"instance '{inst.name}' references unknown vlnv '{inst.vlnv}'")
        comp = components[inst.vlnv]
        used[inst.vlnv] = comp
        register_models[inst.name] = comp.get("memory_maps", [])
    soc = SoC(
        top=top,
        instances=instances,
        components=used,
        connections=connections,
        address_map=address_map,
        register_models=register_models,
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(soc.model_dump_json(indent=2), encoding="utf-8")
    return soc
