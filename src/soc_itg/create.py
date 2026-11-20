import subprocess
from pathlib import Path

SKELETON_DIRS = ["pinmux", "crg", "csr", "rtl", "glue", "ipxact", "filelist", "generated", "release"]
GITIGNORE = "build/\n.soc_itg/\n"

REPO_INFO = """name: {name}
vlnv: {vlnv}
"""
SOC = """design:
  name: {name}
  instances: []
  connections: []
  address_map: []
"""
WORKSPACE = """name: {name}
default_top: {default_top}
repos: []
"""


def scaffold_repo(path, vlnv=""):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for d in SKELETON_DIRS:
        (path / d).mkdir(exist_ok=True)
    (path / f"{path.name}_info.yaml").write_text(
        REPO_INFO.format(name=path.name, vlnv=vlnv or f"local:Local:{path.name}:0.1.0"), encoding="utf-8")
    (path / "soc.yaml").write_text(SOC.format(name=path.name), encoding="utf-8")
    (path / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (path / "README.md").write_text(f"# {path.name}\n", encoding="utf-8")
    return path


def scaffold_workspace(path, default_top=""):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    (path / "workspace.yaml").write_text(WORKSPACE.format(name=path.name, default_top=default_top), encoding="utf-8")
    (path / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (path / "README.md").write_text(f"# {path.name}\n", encoding="utf-8")
    return path


def _git(cwd, args):
    try:
        subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60)
        return True
    except Exception:
        return False


def _git_init(path):
    if not (path / ".git").exists():
        _git(path, ["init", "-q"])
        _git(path, ["add", "-A"])
        _git(path, ["commit", "-q", "-m", "init"])


def _submodule_add(prj_path, sub):
    _git(prj_path, ["submodule", "add", str(Path(sub)), sub])


def create_project(prj, sub=None, init=False, no_git=False, base=None):
    base = Path(base or ".").resolve()
    prj_path = base / prj
    messages = []
    if not prj_path.exists():
        scaffold_workspace(prj_path, default_top=sub or "")
        messages.append(f"workspace {prj_path}")
    if sub:
        sub_path = prj_path / sub
        scaffold_repo(sub_path)
        messages.append(f"repo {sub_path}")
        if not no_git:
            _git_init(prj_path)
            _git_init(sub_path)
            _submodule_add(prj_path, sub)
            if init:
                _git(prj_path, ["submodule", "update", "--init"])
            messages.append("git: submodule added" + (" + init" if init else ""))
    return messages
