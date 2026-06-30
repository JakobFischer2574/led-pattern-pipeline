from __future__ import annotations

import argparse
from pathlib import Path

from led_eval.data.input_validator import validate_inputs
from led_eval.evaluation.aggregation import aggregate_repetitions
from led_eval.evaluation.evaluator import PipelineEvaluator
from led_eval.evaluation.result_writer import snapshot_configs, write_json
from led_eval.utils.config_loader import load_yaml_config
from led_eval.utils.cli_args import positive_int
from led_eval.utils.path_utils import create_run_dir, ensure_dir



def _config_repetitions(config: dict) -> int:
    value = config.get("evaluation", {}).get("repetitions", 1)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit("Konfigurationswert evaluation.repetitions muss eine positive ganze Zahl sein") from exc
    if parsed < 1:
        raise SystemExit("Konfigurationswert evaluation.repetitions muss mindestens 1 sein")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="LED Pattern Evaluation Pipeline")
    parser.add_argument("--config", default="configs/local.yaml")
    parser.add_argument("--method", choices=["classic", "yolo", "both"], default="both")
    parser.add_argument("--stage", choices=["validate", "all"], default="all")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--repetitions", type=positive_int, default=None, help="Anzahl vollständiger Evaluierungsdurchläufe (>= 1)")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_yaml_config(config_path)
    repetitions = args.repetitions if args.repetitions is not None else _config_repetitions(config)
    outputs_dir = config.get("outputs", {}).get("root", "outputs")
    run_name = args.run_name or config.get("run", {}).get("name")
    run_dir = create_run_dir(outputs_dir, run_name)

    validation_report = validate_inputs(config)
    write_json(run_dir / "validation" / "input_validation_report.json", validation_report)
    print(f"Run-Ordner: {run_dir}")
    print(f"Validierung ok: {validation_report['ok']}")
    print(f"Wiederholungen: {repetitions}")

    if args.stage == "validate":
        return
    if not validation_report["ok"]:
        raise SystemExit("Input-Validierung fehlgeschlagen. Details siehe validation/input_validation_report.json")

    config_paths = [
        config_path,
        config.get("classic_cv_config", "configs/classic_cv_config.yaml"),
        config.get("yolo_config", "configs/yolo_config.yaml"),
        config.get("led_layout", "configs/led_layout.yaml"),
        config.get("temporal_config", "configs/temporal_config.yaml"),
        config.get("error_codes_config", "configs/error_codes.yaml"),
    ]
    if repetitions == 1:
        evaluator = PipelineEvaluator(config=config, run_dir=run_dir, config_path=config_path)
        evaluator.run(method=args.method)
    else:
        snapshot_configs(config_paths, run_dir / "run_config_snapshot")
        repetition_dirs = []
        for index in range(1, repetitions + 1):
            rep_dir = ensure_dir(run_dir / "repetitions" / f"run_{index:03d}")
            print(f"Starte Wiederholung {index}/{repetitions}: {rep_dir}")
            evaluator = PipelineEvaluator(config=config, run_dir=rep_dir, config_path=config_path)
            evaluator.run(method=args.method)
            repetition_dirs.append(rep_dir)
        temporal_cfg = load_yaml_config(config.get("temporal_config", "configs/temporal_config.yaml"))
        error_codes = load_yaml_config(config.get("error_codes_config", "configs/error_codes.yaml"))
        aggregate_repetitions(run_dir, repetition_dirs, config_paths, temporal_cfg, error_codes)
    print(f"Pipeline abgeschlossen: {run_dir}")


if __name__ == "__main__":
    main()
