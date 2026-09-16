"""Local supervisor: API, persistent worker and optional CPU model."""

import argparse
import importlib.util
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def available(url):
    try:
        return httpx.get(url, timeout=1).is_success
    except httpx.HTTPError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--without-ai", action="store_true")
    args = parser.parse_args()
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    if available("http://127.0.0.1:8787/api/auth"):
        print("Matchbook is already running: http://127.0.0.1:8787", flush=True)
        if not args.no_browser:
            webbrowser.open("http://127.0.0.1:8787")
        return
    subprocess.run([sys.executable, "-m", "tools.fixtures"], cwd=ROOT, check=True)
    commands = [
        ("app", ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8787"]),
        ("worker", ["-m", "app.worker"]),
    ]
    model_ready = (runtime / "qwen3-0.6b-q8.gguf").exists() and (
        runtime / "qwen3-transformers/tokenizer.json"
    ).exists()
    if (
        not args.without_ai
        and model_ready
        and importlib.util.find_spec("transformers")
        and not available("http://127.0.0.1:8091/v1/models")
    ):
        commands.append(("model", ["-m", "tools.model_server"]))
    processes, logs = [], []
    try:
        for name, command in commands:
            stdout = (runtime / f"{name}.out.log").open("w", encoding="utf-8")
            stderr = (runtime / f"{name}.err.log").open("w", encoding="utf-8")
            logs.extend([stdout, stderr])
            processes.append(
                subprocess.Popen(
                    [sys.executable, *command],
                    cwd=ROOT,
                    stdout=stdout,
                    stderr=stderr,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            )
        for _ in range(60):
            if available("http://127.0.0.1:8787/api/auth"):
                break
            if processes[0].poll() is not None:
                raise RuntimeError("API failed to start. See runtime/app.err.log.")
            time.sleep(0.5)
        else:
            raise RuntimeError("API startup timed out. See runtime/app.err.log.")
        print(
            "Matchbook: http://127.0.0.1:8787\nKeep this window open. Ctrl+C stops this launch.", flush=True
        )
        if not args.no_browser:
            webbrowser.open("http://127.0.0.1:8787")
        while True:
            time.sleep(2)
            if any(p.poll() is not None for p in processes[:2]):
                raise RuntimeError("API or worker stopped. See runtime logs.")
    except KeyboardInterrupt:
        print("Stopping Matchbook services...")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
