from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from led_eval.data.frame_extractor import extract_every_nth_frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrahiert jedes n-te Frame aus einem Video.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--step", type=int, default=30)
    args = parser.parse_args()

    count = extract_every_nth_frame(args.video, args.output, args.step)
    print(f"Gespeicherte Frames: {count}")


if __name__ == "__main__":
    main()

