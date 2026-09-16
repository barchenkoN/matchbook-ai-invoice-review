"""Download data-only model files for the Python runtime; no executable installers."""

import hashlib
import json
import urllib.request

from app.db import ROOT

runtime = ROOT / "runtime"
tokenizer_dir = runtime / "qwen3-transformers"
tokenizer_dir.mkdir(parents=True, exist_ok=True)
assets = [(runtime / "qwen3-0.6b-q8.gguf", "Qwen/Qwen3-0.6B-GGUF", "Qwen3-0.6B-Q8_0.gguf")]
assets += [
    (tokenizer_dir / name, "Qwen/Qwen3-0.6B", name)
    for name in [
        "config.json",
        "generation_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
    ]
]
manifest = []
for target, repo, filename in assets:
    with urllib.request.urlopen("https://huggingface.co/api/models/" + repo) as response:
        revision = json.load(response)["sha"]
    if not target.exists():
        print("Downloading " + filename, flush=True)
        url = f"https://huggingface.co/{repo}/resolve/{revision}/{filename}"
        partial = target.with_suffix(target.suffix + ".part")
        offset = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        with urllib.request.urlopen(request, timeout=60) as response:
            with partial.open("ab" if offset and response.status == 206 else "wb") as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
        partial.replace(target)
    manifest.append(
        {
            "repo": repo,
            "revision_at_check": revision,
            "file": filename,
            "sha256": hashlib.file_digest(target.open("rb"), "sha256").hexdigest(),
            "bytes": target.stat().st_size,
        }
    )
(runtime / "python-model-manifest.json").write_text(json.dumps(manifest, indent=2))
print("Local model data ready. No API key required.")
