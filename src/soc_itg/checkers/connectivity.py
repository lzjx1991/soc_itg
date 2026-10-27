from ..model import SoC


def _finding(level, code, msg, location=""):
    return {"level": level, "code": code, "msg": msg, "location": location}


def _split(endpoint):
    if "." not in endpoint:
        return endpoint, ""
    return tuple(endpoint.split(".", 1))


def _check_instances(soc):
    findings = []
    for inst in soc.instances:
        if inst.vlnv not in soc.components:
            findings.append(_finding("error", "INST_NO_COMPONENT", f"instance '{inst.name}' has no resolved component"))
    return findings


def _check_connections(soc):
    findings = []
    for conn in soc.connections:
        if conn.type == "interconnection":
            for endpoint in (conn.a, conn.b):
                inst_name, iface = _split(endpoint)
                if soc.instance(inst_name) is None:
                    findings.append(_finding("error", "CONN_NO_INST", f"'{endpoint}' references unknown instance"))
                    continue
                comp = soc.component_of(inst_name)
                if comp is not None and comp.bus_if(iface) is None:
                    findings.append(_finding("error", "CONN_NO_IFACE", f"instance '{inst_name}' has no interface '{iface}'"))
        elif conn.type == "adhoc":
            endpoints = [conn.driver] + list(conn.loads)
            for endpoint in endpoints:
                if not endpoint:
                    continue
                inst_name, _ = _split(endpoint)
                if soc.instance(inst_name) is None:
                    findings.append(_finding("error", "CONN_NO_INST", f"'{endpoint}' references unknown instance"))
    return findings


def _check_address(soc):
    findings = []
    regions = []
    for r in soc.address_map:
        try:
            regions.append((r.region, int(r.base, 0), int(r.size, 0)))
        except ValueError:
            findings.append(_finding("error", "ADDR_BAD", f"region '{r.region}' has non-integer base/size"))
    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            r1, b1, s1 = regions[i]
            r2, b2, s2 = regions[j]
            if b1 < b2 + s2 and b2 < b1 + s1:
                findings.append(_finding("error", "ADDR_CONFLICT", f"regions '{r1}' and '{r2}' overlap"))
    return findings


def run_checks(soc: SoC):
    return _check_instances(soc) + _check_connections(soc) + _check_address(soc)
