import yaml
from pathlib import Path
from ..model import Instance, Connection, AddressRegion


def load_soc_yaml(path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    design = data.get("design", data)
    top = design.get("name") or design.get("top") or "top"
    instances = [
        Instance(name=i["name"], vlnv=i["vlnv"], params=i.get("params", {}))
        for i in design.get("instances", [])
    ]
    connections = []
    for c in design.get("connections", []):
        if isinstance(c, str):
            left, right = [s.strip() for s in c.split("=", 1)]
            connections.append(Connection(type="interconnection", a=left, b=right))
        elif isinstance(c, dict):
            connections.append(Connection(**c))
    address_map = [
        AddressRegion(region=r["region"], base=str(r["base"]), size=str(r["size"]))
        for r in design.get("address_map", [])
    ]
    return top, instances, connections, address_map
