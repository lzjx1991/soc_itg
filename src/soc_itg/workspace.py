from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .io.config import load_yaml

WORKSPACE_FILE = "workspace.yaml"


def workspace_dir_of(start):
    root = find_workspace(start)
    base = root if root is not None else Path(start).resolve()
    value = str(base)
    if root is not None:
        config_path = root / WORKSPACE_FILE
        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            workspace_dir = raw.get("workspace_dir")
            if workspace_dir:
                workspace_dir = str(workspace_dir)
                if "${PWD}" in workspace_dir or "$PWD" in workspace_dir:
                    value = str(root)
                else:
                    value = os.path.expandvars(workspace_dir)
    os.environ["workspace_dir"] = value
    return Path(value)


@dataclass
class Repo:
    name: str
    path: Path
    info: dict = field(default_factory=dict)
    soc: dict | None = None

    @property
    def vlnv(self):
        return self.info.get("vlnv")

    @property
    def pinmux_dir(self):
        return self.path / "pinmux"

    @property
    def crg_dir(self):
        return self.path / "crg"

    @property
    def csr_dir(self):
        return self.path / "csr"

    @property
    def rtl_dir(self):
        return self.path / "rtl"

    @property
    def ipxact_dir(self):
        return self.path / "ipxact"

    @property
    def generated_dir(self):
        return self.path / "generated"

    @property
    def build_dir(self):
        return self.path / "build"

    @property
    def info_path(self):
        return self.path / f"{self.path.name}_info.yaml"


@dataclass
class Workspace:
    root: Path
    name: str
    default_top: str | None = None
    repo_names: list[str] = field(default_factory=list)
    repos: dict[str, Repo] = field(default_factory=dict)

    def repo(self, name):
        return self.repos.get(name)

    def resolve(self, name_or_vlnv):
        if name_or_vlnv in self.repos:
            return self.repos[name_or_vlnv]
        for repo in self.repos.values():
            if repo.vlnv == name_or_vlnv:
                return repo
        return None


def find_workspace(start):
    path = Path(start).resolve()
    for candidate in [path, *path.parents]:
        if (candidate / WORKSPACE_FILE).exists():
            return candidate
    return None


def load_repo(path):
    path = Path(path)
    info_path = path / f"{path.name}_info.yaml"
    info = load_yaml(info_path) if info_path.exists() else {}
    soc_path = path / "soc.yaml"
    soc = load_yaml(soc_path) if soc_path.exists() else None
    return Repo(name=path.name, path=path, info=info, soc=soc)


def load_workspace(root):
    root = Path(root)
    config = load_yaml(root / WORKSPACE_FILE)
    names = list(config.get("repos", []) or [])
    workspace = Workspace(
        root=root,
        name=config.get("name", root.name),
        default_top=config.get("default_top"),
        repo_names=names,
    )
    for name in names:
        repo_path = root / name
        if repo_path.is_dir():
            workspace.repos[name] = load_repo(repo_path)
    return workspace


def current_repo(workspace, cwd):
    cwd = Path(cwd).resolve()
    for repo in workspace.repos.values():
        try:
            cwd.relative_to(repo.path.resolve())
            return repo
        except ValueError:
            continue
    return None
