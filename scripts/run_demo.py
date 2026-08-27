#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the LED Pattern Recognition live demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--reload", action="store_true", help="Reload the Python backend during development")
    args = parser.parse_args()
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Demo dependencies are missing. Run: pip install -e '.[demo]'") from exc
    print(f"LED live demo: http://{args.host}:{args.port}")
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        print("Frontend build missing. Run: cd frontend && npm install && npm run build")
    uvicorn.run("led_eval.demo.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
