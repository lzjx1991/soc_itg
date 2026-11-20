from pathlib import Path

from .io.config import load_yaml

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
