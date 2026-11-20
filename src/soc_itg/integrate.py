from pathlib import Path

from .workspace import find_workspace, load_workspace, current_repo, load_repo


def _instances(repo):
    design = (repo.soc or {}).get("design", {}) or {}
    return design.get("instances", []) or []


def integration_order(ws, start):
    order = []
    seen = set()

    def visit(repo):
        if repo.name in seen:
            return
        seen.add(repo.name)
        for inst in _instances(repo):
            if not inst.get("integrate"):
                continue
            ref = inst.get("repo") or inst.get("vlnv")
            dep = ws.resolve(ref) if ref else None
            if dep is not None and dep.name != repo.name:
                visit(dep)
        order.append(repo.name)

    visit(start)
    return order


def plan_integration(cwd):
    cwd = Path(cwd).resolve()
    root = find_workspace(cwd)
    if root is None:
        repo = load_repo(cwd)
        return None, repo, [repo]
    ws = load_workspace(root)
    repo = current_repo(ws, cwd) or ws.repo(ws.default_top) or next(iter(ws.repos.values()))
    order = integration_order(ws, repo)
    return ws, repo, [ws.repos[name] for name in order]
