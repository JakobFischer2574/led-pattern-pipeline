from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from led_eval.yolo.dataset_preparation import copy_annotation_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Kopiert Frames fuer spaetere YOLO-Annotation.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/annotation_candidates")
    parser.add_argument("--step", type=int, default=1)
    args = parser.parse_args()

    copied = copy_annotation_candidates(args.input, args.output, args.step)
    print(f"Kopierte Frames fuer Annotation: {copied}")


if __name__ == "__main__":
    main()

