# led-pattern-evaluation-pipeline

Dieses Repository ist eine modulare Evaluationspipeline fuer die Bachelorarbeit. Es vergleicht zwei visuelle Verfahren zur Analyse von LED-Mustern an Router-Videos:

1. einen klassischen Computer-Vision-Ansatz
2. einen Deep-Learning-Ansatz mit YOLO

Das Repository ist bewusst kein Fork des bisherigen Entwicklungsrepos. Die funktionierenden Detektoren, Classic-CV-Helfer, YOLO-Helfer und Debug-Skripte wurden uebernommen und in eine neue Paketstruktur unter `src/led_eval/` eingeordnet.

## Abgrenzung zum ESP32-Projekt

Das ESP32-Projekt bleibt separat: <https://github.com/JakobFischer2574/esp-led-controller>

Diese Pipeline steuert den ESP32 nicht direkt. Sie verarbeitet nur bereits entstandene Videos und eine Ground-Truth-Datei. Datenerzeugung, LED-Ansteuerung und Experimentsteuerung mit dem ESP32 gehoeren nicht in dieses Repository.

## Zwei Ebenen

### Entwicklungs- und Debug-Ebene

Die Skripte in `scripts/` dienen weiterhin zur Weiterentwicklung und Fehlersuche:

```bash
python scripts/extract_frames.py --video data/raw/videos/video_001.mp4 --output data/sampled_frames/video_001 --step 30
python scripts/inspect_frames.py --frame data/sampled_frames/video_001/video_001_frame_000030.jpg --output data/debug/classic_cv/inspect_video_001_000030.jpg
python scripts/test_classic_cv.py --input data/sampled_frames/video_001 --output-csv outputs/development_runs/classic_cv_video_001.csv
python scripts/prepare_yolo_frames.py --input data/sampled_frames/video_001 --output data/annotation_candidates/video_001 --step 2
python scripts/test_slot_locator.py --input data/sampled_frames/video_001 --config configs/classic_cv_config.yaml --output data/debug/slot_locator
python scripts/test_yolo_detector.py --frame data/sampled_frames/video_001/video_001_frame_000030.jpg --model models/yolo/best.pt
```

Classic CV behaelt die vorhandene ROI-/Slot-Locator-Logik, Debugbilder, `locator_status` und den Fehlerfall `[-1, -1, -1, -1, -1]` bei.

### Evaluationspipeline

Die Pipeline verarbeitet vollstaendige Experimente:

```bash
python scripts/run_pipeline.py --config configs/local.yaml --method both
python scripts/run_pipeline.py --config configs/local.yaml --method classic
python scripts/run_pipeline.py --config configs/local.yaml --method yolo
python scripts/run_pipeline.py --config configs/local.yaml --stage validate
python scripts/run_pipeline.py --config configs/local.yaml --stage all
```

`--stage validate` prueft Ground Truth und Video-Dateien. `--stage all` extrahiert Frames, fuehrt die Detektoren aus, schreibt Frame-Ergebnisse, wendet eine erste temporale Nachverarbeitung an, matcht Fehlercodes und speichert Metriken.

Wenn kein YOLO-Modell unter `models/yolo/best.pt` vorhanden ist oder `ultralytics` fehlt, gibt der YOLO-Detector eine klare Fehlermeldung aus. Bei `--method both` wird diese Fehlermeldung in den Video-Ergebnissen sichtbar, statt still zu scheitern.

## Installation lokal

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Optional fuer YOLO:

```bash
pip install ultralytics
```

## Ground Truth

Die Ground-Truth-Datei ist eine CSV. Beispiel: `data/raw/ground_truth_example.csv`

Pflichtfelder:

- `video_id`
- `file_name`
- `error_code`
- `environment`

`environment` darf nur `labor` oder `real` sein.

Beispielformat:

```csv
video_id,file_name,error_code,environment,recorded_at,lighting,camera_position,distance_cm,notes
1,video_001.mp4,fehlercode_03,labor,2026-06-05T12:00:00,constant,front,80,
2,video_002.mp4,fehlercode_07,real,2026-06-05T12:10:00,daylight,slightly_left,120,
```

Fehlercodes stehen in `configs/error_codes.yaml`.

## Output-Struktur

Jeder Pipeline-Run erzeugt einen eigenen Ordner unter `outputs/`, zum Beispiel:

```text
outputs/local_test_001/
  run_config_snapshot/
  validation/input_validation_report.json
  frame_results/classic/
  frame_results/yolo/
  temporal_results/
  video_results.csv
  latency_metrics.csv
  resource_metrics.csv
  plots/
  summary.json
```

Frame-Ergebnisse enthalten pro Frame LED-Zustand, Konfidenzen, Processing Time und Locator-Status. Video-Ergebnisse enthalten vorhergesagten Fehlercode, Accuracy-Flag, Latenz, CPU und Peak-RAM.

## Docker

CPU-Container:

```bash
docker compose build led-eval-cpu
docker compose run --rm led-eval-cpu
```

Server-Mounts in `docker-compose.yml`:

```yaml
volumes:
  - /srv/led-eval/data:/data
  - /srv/led-eval/models:/models
  - /srv/led-eval/outputs:/outputs
```

`configs/server.yaml` verweist auf diese gemounteten Pfade.

## Daten im Git-Repo

Grosse Videos, Modelle, extrahierte Frames, Debugbilder und Outputs gehoeren nicht ins Git-Repo. Die entsprechenden Ordner sind in `.gitignore` ausgeschlossen. Leere `.gitkeep`-Dateien halten nur die erwartete Ordnerstruktur sichtbar.

## Analyse

`scripts/run_analysis.py` bereitet erste Tabellen vor:

- Accuracy nach Methode
- Accuracy nach Umgebung
- Latenzvergleich Classic vs. YOLO
- CPU/RAM-Vergleich

Statistische Tests wie Wilcoxon und McNemar sind als Module vorbereitet und koennen nach Festlegung der finalen gepaarten Auswertung erweitert werden.
