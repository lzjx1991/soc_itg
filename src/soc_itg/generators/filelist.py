from pathlib import Path

from ..ipxact.resolve import repo_components


def _strip_and_join(text):
    lines = []
    buf = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].split("//", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        lines.append((buf + line).strip())
        buf = ""
    if buf:
        lines.append(buf.strip())
    return " ".join(lines).split()


def parse_filelist(path, _depth=0):
    path = Path(path)
    base = path.parent
    result = {"incdirs": [], "defines": [], "lib_dirs": [], "lib_files": [], "files": []}
    if _depth > 10:
        return result
    tokens = _strip_and_join(path.read_text(encoding="utf-8", errors="ignore"))
    i = 0
    while i < len(tokens):
        token = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if token == "-y" and nxt is not None:
            result["lib_dirs"].append(nxt); i += 2; continue
        if token == "-v" and nxt is not None:
            result["lib_files"].append(nxt); i += 2; continue
        if token == "-f" and nxt is not None:
            nested = parse_filelist(base / nxt, _depth + 1)
            for k in result:
                result[k].extend(nested[k])
            i += 2; continue
        if token.startswith("+incdir+"):
            result["incdirs"].extend(d for d in token[len("+incdir+"):].split("+") if d); i += 1; continue
        if token.startswith("+define+"):
            result["defines"].append(token[len("+define+"):]); i += 1; continue
        if token.startswith("-I") and len(token) > 2:
            result["incdirs"].append(token[2:]); i += 1; continue
        if token.startswith("-D") and len(token) > 2:
            result["defines"].append(token[2:]); i += 1; continue
        if token.startswith("-"):
            i += 1; continue
        result["files"].append(token); i += 1
    return result


def _is_package(path, file_type):
    name = Path(path).name.lower()
    return "pkg" in name or name.endswith(".svh") or "package" in file_type.lower()


def collect_files(repo, top_name=None):
    entries = []
    for comp in repo_components(repo).values():
        for file_set in comp.file_sets:
            for item in file_set.files:
                entries.append((str(repo.path / item.name), item.file_type))
    generated_rtl = repo.path / "generated" / "rtl"
    if generated_rtl.exists():
        for f in sorted(generated_rtl.rglob("*")):
            if f.suffix in (".v", ".sv", ".svh"):
                file_type = "verilogSource" if f.suffix == ".v" else "systemVerilogSource"
                entries.append((str(f), file_type))
    seen = set()
    unique = []
    for path, file_type in entries:
        if path in seen:
            continue
        seen.add(path)
        unique.append((path, file_type))
    return unique


def _ordered(entries, top_name):
    def key(entry):
        path, file_type = entry
        if _is_package(path, file_type):
            return (0, path)
        if top_name and Path(path).stem.lower() == top_name.lower():
            return (2, path)
        return (1, path)
    return sorted(entries, key=key)


def generate_filelists(repo, top_name=None):
    entries = _ordered(collect_files(repo, top_name), top_name)
    files = [path for path, _ in entries]
    outdir = repo.path / "generated" / "filelist"
    outdir.mkdir(parents=True, exist_ok=True)
    incdirs = sorted({str(Path(p).parent) for p in files})

    sim_lines = [f"+incdir+{d}" for d in incdirs] + files
    (outdir / "sim.f").write_text("\n".join(sim_lines) + "\n", encoding="utf-8")
    (outdir / "syn.f").write_text("\n".join(files) + "\n", encoding="utf-8")
    (outdir / "fpga.f").write_text("\n".join(files) + "\n", encoding="utf-8")
    return {"files": files, "incdirs": incdirs, "outdir": outdir}
