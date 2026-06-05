from __future__ import annotations

from datetime import datetime
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_run_dir(outputs_dir: str | Path, run_name: str | None = None) -> Path:
    root = ensure_dir(outputs_dir)
    name = run_name or datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir = root / name
    suffix = 1
    while run_dir.exists():
        run_dir = root / f"{name}_{suffix:02d}"
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir
