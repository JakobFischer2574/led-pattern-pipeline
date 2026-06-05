from pathlib import Path

from led_eval.data.input_validator import validate_inputs


def test_validate_inputs_reports_missing_videos(tmp_path: Path) -> None:
    gt = tmp_path / "ground_truth.csv"
    gt.write_text(
        "video_id,file_name,error_code,environment\n"
        "1,missing.mp4,fehlercode_03,labor\n",
        encoding="utf-8",
    )
    video_dir = tmp_path / "videos"
    video_dir.mkdir()

    report = validate_inputs({"data": {"ground_truth_csv": str(gt), "video_dir": str(video_dir)}})

    assert report["ok"] is False
    assert len(report["missing_videos"]) == 1
