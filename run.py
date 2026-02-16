import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    root_dir = Path(__file__).resolve().parent
    load_dotenv(root_dir / ".env")

    parser = argparse.ArgumentParser(description="Run the CodeAssist FastAPI backend")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", default=os.getenv("RELOAD", "0") == "1")
    args = parser.parse_args()

    backend_dir = root_dir / "backend"

    if not backend_dir.exists():
        print(f"Backend directory not found: {backend_dir}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--app-dir",
        str(backend_dir),
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    if args.reload:
        cmd.append("--reload")

    print("Starting backend with:", " ".join(cmd))
    try:
        return subprocess.call(cmd, cwd=str(root_dir))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
