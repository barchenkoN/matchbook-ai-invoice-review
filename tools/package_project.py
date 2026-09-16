"""Allowlisted shareable artifact; excludes documents uploaded by the user and runtimes."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
output = ROOT.parent / "output"
output.mkdir(exist_ok=True)
files = [
    p for p in ROOT.iterdir() if p.is_file() and p.suffix in (".md", ".toml", ".json", ".txt", ".ps1", ".cmd")
]
files += [ROOT / ".gitignore", ROOT / ".env.example"]
for folder in ["app", "tools", "tests", "docs", "fixtures", "workflows", "frontend/src", "frontend/dist"]:
    files += [
        p
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]
files += [
    ROOT / "frontend" / name
    for name in ["package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "tsconfig.json", "index.html"]
]
target = output / "Matchbook-Portfolio-Project.zip"
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        if path.exists():
            archive.write(path, Path("Matchbook") / path.relative_to(ROOT))
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    names = archive.namelist()
    assert not any(
        "/runtime/" in n or "/data/" in n or "/.venv/" in n or "/node_modules/" in n for n in names
    )
report = {
    "file": target.name,
    "files": len(names),
    "bytes": target.stat().st_size,
    "sha256": hashlib.file_digest(target.open("rb"), "sha256").hexdigest(),
}
(output / "Matchbook-package-manifest.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
