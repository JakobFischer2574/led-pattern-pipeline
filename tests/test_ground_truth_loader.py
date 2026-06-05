from pathlib import Path

import pytest

from led_eval.data.ground_truth_loader import load_ground_truth


def test_load_ground_truth_accepts_expected_schema(tmp_path: Path) -> None:
    csv_path = tmp_path / "gt.csv"
    csv_path.write_text(
        "video_id,file_name,error_code,environment\n"
        "1,video_001.mp4,fehlercode_03,labor\n",
        encoding="utf-8",
    )

    df = load_ground_truth(csv_path)

    assert list(df["file_name"]) == ["video_001.mp4"]


def test_load_ground_truth_rejects_invalid_environment(tmp_path: Path) -> None:
    csv_path = tmp_path / "gt.csv"
    csv_path.write_text(
        "video_id,file_name,error_code,environment\n"
        "1,video_001.mp4,fehlercode_03,studio\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="environment"):
        load_ground_truth(csv_path)
