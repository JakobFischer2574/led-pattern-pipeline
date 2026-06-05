from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"video_id", "file_name", "error_code", "environment"}
VALID_ENVIRONMENTS = {"labor", "real"}


@dataclass(frozen=True)
class GroundTruthValidation:
    rows: int
    missing_columns: list[str]
    invalid_environments: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing_columns and not self.invalid_environments


def load_ground_truth(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Ground-Truth CSV nicht gefunden: {path}")
    df = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing:
        raise ValueError(f"Ground-Truth CSV hat fehlende Spalten: {missing}")
    invalid = sorted(set(df["environment"].dropna().astype(str)) - VALID_ENVIRONMENTS)
    if invalid:
        raise ValueError(f"Ungueltige environment-Werte: {invalid}. Erlaubt: {sorted(VALID_ENVIRONMENTS)}")
    return df


def validate_ground_truth(csv_path: str | Path) -> GroundTruthValidation:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Ground-Truth CSV nicht gefunden: {path}")
    df = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS.difference(df.columns))
    invalid: list[str] = []
    if "environment" in df.columns:
        invalid = sorted(set(df["environment"].dropna().astype(str)) - VALID_ENVIRONMENTS)
    return GroundTruthValidation(rows=len(df), missing_columns=missing, invalid_environments=invalid)

