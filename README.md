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

## Mehrere Evaluierungsdurchläufe und Server-Ausführung

Die Pipeline kann dieselbe Evaluation mehrfach vollständig ausführen und anschließend stabile Endergebnisse aggregieren. Beispiel lokal:

```bash
python scripts/run_pipeline.py \
  --config configs/local.yaml \
  --method both \
  --run-name final_evaluation_run_01 \
  --repetitions 20
```

`--repetitions` muss eine positive ganze Zahl sein. Wird der Parameter nicht angegeben, verwendet die Pipeline `evaluation.repetitions` aus der YAML-Konfiguration oder standardmäßig `1`. Bei `1` bleibt der klassische Ablauf erhalten: `video_results.csv`, `latency_metrics.csv`, `resource_metrics.csv`, `summary.json`, `frame_results/` und `temporal_results/` liegen direkt im Run-Ordner.

Bei mehreren Wiederholungen führt jede Wiederholung die Detektionsschleife erneut aus und verwendet einen neuen `ResourceMonitor`. Bereits extrahierte Frames dürfen wiederverwendet werden, weil die Frame-Extraktion nicht Teil der gemessenen Detektionslatenz ist; `processing_time_ms` misst weiterhin nur die Detektion pro Frame. Die Einzelresultate bleiben unter `repetitions/run_001/`, `repetitions/run_002/` usw. erhalten. Die Dateien direkt im finalen Run-Ordner enthalten aggregierte Resultate, damit bestehende Analyse-Skripte weiterhin `outputs/<run-name>/video_results.csv` lesen können.

Finale Output-Struktur bei mehreren Wiederholungen:

```text
outputs/final_evaluation_run_01/
  run_config_snapshot/
  validation/
  repetitions/
    run_001/
      frame_results/
      temporal_results/
      video_results.csv
      latency_metrics.csv
      resource_metrics.csv
      summary.json
    run_002/
      ...
  repetition_video_results.csv
  aggregate_metadata.json
  video_results.csv
  latency_metrics.csv
  resource_metrics.csv
  frame_results/
  temporal_results/
  summary.json
```

Aggregation:

- Video-Ergebnisse werden nach `video_id`, `file_name`, `environment`, `method` und `true_error_code` gruppiert.
- Numerische Messmetriken werden als Median der bereits fertigen Video-Ergebnisse pro Wiederholung berechnet. Frame-Zeiten aus verschiedenen Wiederholungen werden nicht direkt zusammengeworfen.
- `predicted_error_code` wird per Mehrheitsentscheidung aggregiert. Bei Gleichstand entscheidet die lexikografisch kleinste String-Repräsentation deterministisch.
- `correct` wird aus dem finalen `predicted_error_code` und `true_error_code` neu berechnet.
- Zusätzlich werden `correct_rate`, `correct_repetitions`, `total_repetitions` und `prediction_consistency` geschrieben.
- Frame-Ergebnisse werden nach `video_id`, `method` und `frame_index` gruppiert. Numerische Werte wie Konfidenzen und `processing_time_ms` nutzen den Median; LED-Zustände und `locator_status` nutzen den Modus mit derselben deterministischen Tie-Break-Regel.
- Finale temporale Ergebnisse werden aus den aggregierten LED-Sequenzen neu berechnet und in `temporal_results/` gespeichert.

### Server-Lauf mit tmux

Für robuste Server-Ausführungen stehen zwei Skripte bereit:

```bash
bash scripts/server/start_evaluation_tmux.sh \
  --config configs/server.yaml \
  --method both \
  --run-name final_evaluation_run_01 \
  --repetitions 20 \
  --session led-eval-final-01
```

`start_evaluation_tmux.sh` prüft, ob `tmux` vorhanden ist, verweigert das Überschreiben vorhandener Sessions und startet `scripts/server/run_evaluation_server.sh` detached mit `remain-on-exit`, damit Abschluss- und Fehlermeldungen sichtbar bleiben.

`run_evaluation_server.sh` wechselt zum Repository-Root, bricht bei uncommitted Git-Änderungen ab, führt `git fetch --prune` und `git pull --ff-only` aus, lädt vorhandene Git-LFS-Dateien mit `git lfs pull`, aktiviert optional `.venv/bin/activate` oder verwendet `PYTHON_BIN`, prüft die in der Server-Config referenzierten Eingabe-, Modell- und Output-Pfade und startet dann die Pipeline. Die Ausgabe wird gleichzeitig in tmux und nach `outputs/<run-name>/server_run.log` geschrieben.

Nützliche Befehle zur Überwachung:

```bash
tmux attach -t led-eval-final-01
tmux capture-pane -pt led-eval-final-01
tail -f outputs/final_evaluation_run_01/server_run.log
```

Videos liegen häufig nicht in Git. Stellen Sie diese vor dem Start per Server-Mount oder manuellem Transfer bereit, z. B. mit einem projektspezifischen `rsync`-Befehl auf den in `configs/server.yaml` konfigurierten Pfad. Die Skripte löschen, verschieben oder erfinden keine Videodaten und brechen mit einer verständlichen Fehlermeldung ab, wenn benötigte Pfade fehlen.
