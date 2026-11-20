from pathlib import Path

from .io.config import load_yaml
from .generators.filelist import parse_filelist

TOOLS = ["syn", "cdc_check", "upf_check", "lint_check", "sdc_check"]


def load_repo_info(repo):
    path = repo.path / f"{repo.name}_info.yaml"
    return load_yaml(path) if path.exists() else {}


def plan_flow(repo, tool, tops=None):
    info = load_repo_info(repo)
    tasks = info.get(tool) or []
    plans = []
    for task in tasks:
        top = task.get("top")
        if tops and top not in tops:
            continue
        plans.append(dict(task))
    return plans


def flow_command(tool, task):
    parts = [f"soc-itg flow {tool}"]
    if task.get("top"):
        parts.append(f"--top {task['top']}")
    for key in ("sdc", "upf", "waive"):
        if task.get(key):
            value = task[key]
            if isinstance(value, list):
                value = " ".join(str(v) for v in value)
            parts.append(f"--{key} {value}")
    return " ".join(parts)


def _derive_deps(repo):
    design = (repo.soc or {}).get("design", {}) or {}
    deps = []
    for inst in design.get("instances", []):
        ref = inst.get("repo") or inst.get("vlnv")
        if ref and ref not in deps:
            deps.append(ref)
    return deps


def dependence(repo):
    design = (repo.soc or {}).get("design", {}) or {}
    declared = design.get("dependence")
    return list(declared) if declared else _derive_deps(repo)


def workspace_dir(repo):
    from .workspace import workspace_dir_of
    return workspace_dir_of(repo.path)


def gather_filelist(repo, workspace, tool):
    kind = {"verdi": "sim", "vcs": "sim", "dc": "syn"}.get(tool, "sim")
    incdirs, defines, files = [], [], []
    seen = set()

    def absorb(path):
        if not path or not Path(path).exists():
            return
        parsed = parse_filelist(path)
        for d in parsed["incdirs"]:
            if d not in incdirs:
                incdirs.append(d)
        for d in parsed["defines"]:
            if d not in defines:
                defines.append(d)
        for f in parsed["files"]:
            if f not in seen:
                seen.add(f)
                files.append(f)

    for ref in dependence(repo):
        dep = workspace.resolve(ref) if workspace is not None else None
        if dep is None:
            continue
        absorb((load_repo_info(dep).get("filelist") or {}).get(kind))
    absorb((load_repo_info(repo).get("filelist") or {}).get(kind))
    return {"incdirs": incdirs, "defines": defines, "files": files}
