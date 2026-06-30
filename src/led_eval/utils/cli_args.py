from __future__ import annotations

import argparse


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--repetitions muss eine positive ganze Zahl sein") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("--repetitions muss mindestens 1 sein")
    return parsed
