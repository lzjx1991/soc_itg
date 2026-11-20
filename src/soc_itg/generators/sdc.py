from pathlib import Path


def merge_sdc(repo):
    sdc_dir = repo.path / "generated" / "sdc"
    sdc_dir.mkdir(parents=True, exist_ok=True)
    out = sdc_dir / f"{repo.name}.sdc"
    sources = [s for s in sorted(sdc_dir.glob("*.sdc")) if s.resolve() != out.resolve()]
    lines = ["// merged sdc (soc-itg)"]
    for source in sources:
        lines.append(f"// === {source.name} ===")
        lines.append(source.read_text(encoding="utf-8", errors="ignore"))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
