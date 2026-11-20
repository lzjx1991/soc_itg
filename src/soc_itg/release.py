import json
import shutil
from pathlib import Path


def release(repo, version):
    base = repo.path if hasattr(repo, "path") else Path(repo)
    base = Path(base)
    source = base / "generated"
    out = base / "release" / version
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    if source.exists():
        shutil.copytree(source, out / "generated")
    (out / "manifest.json").write_text(json.dumps({"version": version, "generated": "generated"}, indent=2), encoding="utf-8")
    return out
