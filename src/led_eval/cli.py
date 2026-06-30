from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from led_eval.data.input_validator import validate_inputs
from led_eval.evaluation.aggregation import aggregate_repetitions
from led_eval.evaluation.evaluator import PipelineEvaluator
from led_eval.evaluation.result_writer import snapshot_configs, write_json
from led_eval.utils.cli_args import positive_int
from led_eval.utils.config_loader import load_yaml_config
from led_eval.utils.path_utils import create_run_dir, ensure_dir


def _config_repetitions(config: dict) -> int:
    value = config.get("evaluation", {}).get("repetitions", 1)

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            "Konfigurationswert evaluation.repetitions muss eine positive ganze Zahl sein"
        ) from exc

    if parsed < 1:
        raise SystemExit(
            "Konfigurationswert evaluation.repetitions muss mindestens 1 sein"
        )

    return parsed


def _concat_csv_files(destination: Path, sources: list[Path]) -> None:
    """Führt CSV-Dateien mit derselben Tabellenstruktur zeilenweise zusammen."""
    fieldnames: list[str] = []
    rows: list[dict[str, str]] = []

    for source in sources:
        if not source.exists():
            continue

        with source.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)

            if not reader.fieldnames:
                continue

            for fieldname in reader.fieldnames:
                if fieldname not in fieldnames:
                    fieldnames.append(fieldname)

            rows.extend(reader)

    if not fieldnames:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def _move_tree_contents(source: Path, destination: Path) -> None:
    """Verschiebt alle Dateien aus source nach destination ohne Überschreiben."""
    if not source.exists():
        return

    destination.mkdir(parents=True, exist_ok=True)

    for source_item in source.iterdir():
        destination_item = destination / source_item.name

        if source_item.is_dir():
            if destination_item.exists():
                if not destination_item.is_dir():
                    raise FileExistsError(
                        f"Kann Verzeichnis nicht zusammenführen: {destination_item}"
                    )

                _move_tree_contents(source_item, destination_item)
                source_item.rmdir()
            else:
                shutil.move(str(source_item), str(destination_item))

        else:
            if destination_item.exists():
                raise FileExistsError(
                    f"Datei würde überschrieben werden: {destination_item}"
                )

            shutil.move(str(source_item), str(destination_item))


def _merge_worker_outputs(
    repetition_dir: Path,
    worker_dirs: dict[str, Path],
) -> None:
    """
    Führt die getrennten Classic- und YOLO-Worker-Ergebnisse zu einem
    vollständigen Wiederholungsordner zusammen.
    """
    for csv_name in (
        "video_results.csv",
        "latency_metrics.csv",
        "resource_metrics.csv",
    ):
        _concat_csv_files(
            repetition_dir / csv_name,
            [worker_dir / csv_name for worker_dir in worker_dirs.values()],
        )

    worker_summaries: dict[str, object] = {}

    for method, worker_dir in worker_dirs.items():
        summary_path = worker_dir / "summary.json"

        if summary_path.exists():
            worker_summaries[method] = json.loads(
                summary_path.read_text(encoding="utf-8")
            )

        _move_tree_contents(
            worker_dir / "frame_results",
            repetition_dir / "frame_results",
        )

        _move_tree_contents(
            worker_dir / "temporal_results",
            repetition_dir / "temporal_results",
        )

    write_json(
        repetition_dir / "summary.json",
        {
            "execution_mode": "isolated_python_process_per_method",
            "methods": worker_summaries,
        },
    )

    workers_root = repetition_dir / "_workers"

    if workers_root.exists():
        shutil.rmtree(workers_root)


def _run_worker(
    config_path: Path,
    method: str,
    worker_dir: Path,
) -> None:
    """
    Startet eine Methode in einem frischen Python-Prozess.
    Dadurch kann zuvor geladener YOLO-Speicher nicht in die
    Classic-RAM-Messung der nächsten Wiederholung übergehen.
    """
    repository_root = Path(__file__).resolve().parents[2]
    runner_script = repository_root / "scripts" / "run_pipeline.py"

    command = [
        sys.executable,
        str(runner_script),
        "--config",
        str(config_path),
        "--method",
        method,
        "--worker-run-dir",
        str(worker_dir),
    ]

    print(f"  Starte isolierten {method}-Worker: {worker_dir}")
    subprocess.run(command, check=True)


def _run_worker_mode(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    config: dict,
    config_path: Path,
) -> None:
    """
    Interner Ausführungsmodus: genau eine Methode in genau einem
    frischen Prozess und in einem vorgegebenen Ausgabeordner.
    """
    if args.method not in {"classic", "yolo"}:
        parser.error(
            "--worker-run-dir darf nur mit --method classic oder --method yolo "
            "verwendet werden."
        )

    if args.repetitions not in (None, 1):
        parser.error(
            "--worker-run-dir führt genau einen Worker-Lauf aus und akzeptiert "
            "keine mehreren Wiederholungen."
        )

    worker_dir = ensure_dir(args.worker_run_dir)

    validation_report = validate_inputs(config)
    write_json(
        worker_dir / "validation" / "input_validation_report.json",
        validation_report,
    )

    if not validation_report["ok"]:
        raise SystemExit(
            "Input-Validierung fehlgeschlagen. "
            "Details siehe validation/input_validation_report.json"
        )

    evaluator = PipelineEvaluator(
        config=config,
        run_dir=worker_dir,
        config_path=config_path,
    )
    evaluator.run(method=args.method)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LED Pattern Evaluation Pipeline"
    )

    parser.add_argument("--config", default="configs/local.yaml")
    parser.add_argument(
        "--method",
        choices=["classic", "yolo", "both"],
        default="both",
    )
    parser.add_argument(
        "--stage",
        choices=["validate", "all"],
        default="all",
    )
    parser.add_argument("--run-name", default=None)
    parser.add_argument(
        "--repetitions",
        type=positive_int,
        default=None,
        help="Anzahl vollständiger Evaluierungsdurchläufe (>= 1)",
    )

    # Nur für den internen Subprocess-Aufruf; nicht für normale Nutzung gedacht.
    parser.add_argument(
        "--worker-run-dir",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )

    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_yaml_config(config_path)

    # Worker beendet sich hier direkt nach genau einer Methode.
    if args.worker_run_dir is not None:
        _run_worker_mode(args, parser, config, config_path)
        return

    repetitions = (
        args.repetitions
        if args.repetitions is not None
        else _config_repetitions(config)
    )

    outputs_dir = config.get("outputs", {}).get("root", "outputs")
    run_name = args.run_name or config.get("run", {}).get("name")
    run_dir = create_run_dir(outputs_dir, run_name)

    validation_report = validate_inputs(config)

    write_json(
        run_dir / "validation" / "input_validation_report.json",
        validation_report,
    )

    print(f"Run-Ordner: {run_dir}")
    print(f"Validierung ok: {validation_report['ok']}")
    print(f"Wiederholungen: {repetitions}")

    if args.stage == "validate":
        return

    if not validation_report["ok"]:
        raise SystemExit(
            "Input-Validierung fehlgeschlagen. "
            "Details siehe validation/input_validation_report.json"
        )

    config_paths = [
        config_path,
        config.get("classic_cv_config", "configs/classic_cv_config.yaml"),
        config.get("yolo_config", "configs/yolo_config.yaml"),
        config.get("led_layout", "configs/led_layout.yaml"),
        config.get("temporal_config", "configs/temporal_config.yaml"),
        config.get("error_codes_config", "configs/error_codes.yaml"),
    ]

    # Unveränderter, kompatibler Einzelrun.
    if repetitions == 1:
        evaluator = PipelineEvaluator(
            config=config,
            run_dir=run_dir,
            config_path=config_path,
        )
        evaluator.run(method=args.method)

    else:
        snapshot_configs(
            config_paths,
            run_dir / "run_config_snapshot",
        )

        methods = (
            ["classic", "yolo"]
            if args.method == "both"
            else [args.method]
        )

        repetition_dirs: list[Path] = []

        for index in range(1, repetitions + 1):
            repetition_dir = ensure_dir(
                run_dir / "repetitions" / f"run_{index:03d}"
            )

            print(
                f"Starte Wiederholung {index}/{repetitions}: "
                f"{repetition_dir}"
            )

            worker_dirs: dict[str, Path] = {}

            for method in methods:
                worker_dir = ensure_dir(
                    repetition_dir / "_workers" / method
                )

                _run_worker(
                    config_path=config_path,
                    method=method,
                    worker_dir=worker_dir,
                )

                worker_dirs[method] = worker_dir

            _merge_worker_outputs(
                repetition_dir=repetition_dir,
                worker_dirs=worker_dirs,
            )

            repetition_dirs.append(repetition_dir)

        temporal_cfg = load_yaml_config(
            config.get(
                "temporal_config",
                "configs/temporal_config.yaml",
            )
        )

        error_codes = load_yaml_config(
            config.get(
                "error_codes_config",
                "configs/error_codes.yaml",
            )
        )

        aggregate_repetitions(
            run_dir,
            repetition_dirs,
            config_paths,
            temporal_cfg,
            error_codes,
        )

    print(f"Pipeline abgeschlossen: {run_dir}")


if __name__ == "__main__":
    main()