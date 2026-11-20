def check(workspace):
    findings = []
    for name in workspace.repo_names:
        repo = workspace.repo(name)
        if repo is None or not repo.path.exists():
            findings.append({"level": "error", "code": "REPO_MISSING", "msg": f"repo '{name}' missing or not loaded"})
    return findings
