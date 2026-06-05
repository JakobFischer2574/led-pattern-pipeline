from __future__ import annotations

import argparse
from pathlib import Path

from led_eval.data.input_validator import validate_inputs
from led_eval.evaluation.evaluator import PipelineEvaluator
from led_eval.evaluation.result_writer import write_json
from led_eval.utils.config_loader import load_yaml_config
from led_eval.utils.path_utils import create_run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="LED Pattern Evaluation Pipeline")
    parser.add_argument("--config", default="configs/local.yaml")
    parser.add_argument("--method", choices=["classic", "yolo", "both"], default="both")
    parser.add_argument("--stage", choices=["validate", "all"], default="all")
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_yaml_config(config_path)
    outputs_dir = config.get("outputs", {}).get("root", "outputs")
    run_name = args.run_name or config.get("run", {}).get("name")
    run_dir = create_run_dir(outputs_dir, run_name)

    validation_report = validate_inputs(config)
    write_json(run_dir / "validation" / "input_validation_report.json", validation_report)
    print(f"Run-Ordner: {run_dir}")
    print(f"Validierung ok: {validation_report['ok']}")

    if args.stage == "validate":
        return
    if not validation_report["ok"]:
        raise SystemExit("Input-Validierung fehlgeschlagen. Details siehe validation/input_validation_report.json")

    evaluator = PipelineEvaluator(config=config, run_dir=run_dir, config_path=config_path)
    evaluator.run(method=args.method)
    print(f"Pipeline abgeschlossen: {run_dir}")


if __name__ == "__main__":
    main()
