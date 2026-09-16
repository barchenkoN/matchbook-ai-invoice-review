"""Record dependency and source provenance without secrets or user documents."""

import hashlib
import importlib.metadata
import json
import platform

from app.db import ROOT

packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions() if d.metadata["Name"]}
sources = {}
for folder in ["app", "tools", "frontend/src"]:
    for path in sorted((ROOT / folder).rglob("*")):
        if path.is_file() and path.suffix in (".py", ".tsx", ".ts", ".css"):
            sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
model_path = ROOT / "runtime/qwen3-0.6b-q8.gguf"
record = {
    "python": platform.python_version(),
    "platform": platform.system(),
    "packages": packages,
    "source_sha256": sources,
    "model_sha256": hashlib.file_digest(model_path.open("rb"), "sha256").hexdigest()
    if model_path.exists()
    else None,
}
(ROOT / "docs/evidence/release-environment.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print("Release dependency and source snapshot saved.")
