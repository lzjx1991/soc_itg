from pathlib import Path

from .reader import read_component


def _repo_ipxact_dir(repo):
    d = getattr(repo, "ipxact_dir", None)
    return Path(d) if d is not None else Path(repo) / "ipxact"


def repo_components(repo):
    result = {}
    directory = _repo_ipxact_dir(repo)
    if directory.exists():
        for f in sorted(directory.rglob("*.xml")):
            comp = read_component(f)
            result[comp.vlnv] = comp
    return result


def resolve(workspace, name_or_vlnv):
    repo = workspace.resolve(name_or_vlnv)
    if repo is None:
        return None, None
    components = repo_components(repo)
    if name_or_vlnv in components:
        return repo, components[name_or_vlnv]
    if components:
        return repo, next(iter(components.values()))
    return repo, None
