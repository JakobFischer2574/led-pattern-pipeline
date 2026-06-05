from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from led_eval.analysis.plots import write_analysis_tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Erzeugt erste Analyse-Tabellen aus video_results.csv.")
    parser.add_argument("--video-results", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_analysis_tables(args.video_results, args.output)
    print(f"Analyse-Tabellen gespeichert: {args.output}")


if __name__ == "__main__":
    main()
