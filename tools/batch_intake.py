"""Working API client example: enqueue a folder without UI or direct database access."""

import argparse
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("folder", type=Path)
parser.add_argument("--mode", choices=["local", "replay"], default="local")
args = parser.parse_args()
with httpx.Client(base_url="http://127.0.0.1:8787", timeout=30) as client:
    response = client.post("/api/login", json={"role": "reviewer"})
    response.raise_for_status()
    for path in sorted(args.folder.iterdir()):
        if path.suffix.lower() not in (".pdf", ".png", ".jpg", ".jpeg"):
            continue
        with path.open("rb") as file:
            result = client.post("/api/invoices", data={"mode": args.mode}, files={"file": (path.name, file)})
        result.raise_for_status()
        print(path.name, result.json())
