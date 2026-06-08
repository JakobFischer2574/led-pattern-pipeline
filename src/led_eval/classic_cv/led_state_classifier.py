def classify_led_state(features: dict[str, float], thresholds: dict[str, float]) -> tuple[int, float]:
    """
    Klassifiziert eine LED als ON/OFF.

    Logik:
    - Grün/LED-Fläche muss vorhanden sein.
    - Zusätzlich muss ein Aktivitätsmerkmal vorhanden sein:
      entweder deutliche Helligkeit oder gültiger weißer LED-Kern.

    Dadurch wird verhindert, dass ausgeschaltete, aber grünliche LED-Kappen
    fälschlich als ON klassifiziert werden.
    """

    green_pixel_ratio = float(features.get("green_pixel_ratio", 0.0))
    max_green_score = float(features.get("max_green_score", 0.0))
    largest_green_component_area = float(features.get("largest_green_component_area", 0.0))

    largest_component_area = float(
        features.get(
            "combined_largest_component_area",
            features.get("largest_green_component_area", 0.0),
        )
    )

    max_brightness = float(
        features.get(
            "max_brightness",
            features.get("bright_max", 0.0),
        )
    )

    bright_pixel_ratio = float(features.get("bright_pixel_ratio", 0.0))
    valid_white_core_area = float(features.get("valid_white_core_area", 0.0))

    min_green_pixel_ratio = float(thresholds.get("min_green_pixel_ratio", 0.08))
    min_max_green_score = float(thresholds.get("min_max_green_score", 180.0))
    min_largest_green_component_area = float(thresholds.get("min_largest_green_component_area", 100.0))

    min_valid_white_core_area = float(thresholds.get("min_valid_white_core_area", 8.0))

    min_max_brightness = float(thresholds.get("min_max_brightness", 220.0))
    min_bright_max = float(
        thresholds.get(
            "min_bright_max",
            thresholds.get("min_max_brightness", 230.0),
        )
    )
    min_bright_pixel_ratio = float(thresholds.get("min_bright_pixel_ratio", 0.1))
    min_combined_component_area = float(thresholds.get("min_combined_component_area", 80.0))

    # 1. Ist grundsätzlich eine LED / grüne LED-Kappe in der ROI vorhanden?
    green_checks = [
        green_pixel_ratio >= min_green_pixel_ratio,
        max_green_score >= min_max_green_score,
        largest_green_component_area >= min_largest_green_component_area,
        largest_component_area >= min_combined_component_area,
    ]

    green_found = all(green_checks)


    bright_checks = [
        max_brightness >= min_bright_max,
        bright_pixel_ratio >= min_bright_pixel_ratio,
    ]

    bright_found = all(bright_checks)


    white_core_checks = [
        valid_white_core_area >= min_valid_white_core_area,
        max_brightness >= min_max_brightness,
        bright_pixel_ratio >= min_bright_pixel_ratio,
    ]

    white_core_found = all(white_core_checks)

    # Finale ON-Logik:
    # Grüne LED-Struktur muss vorhanden sein UND zusätzlich Helligkeit/White-Core.
    is_on = green_found and (bright_found or white_core_found)

    green_confidence = sum(float(v) for v in green_checks) / len(green_checks)
    bright_confidence = sum(float(v) for v in bright_checks) / len(bright_checks)
    white_confidence = sum(float(v) for v in white_core_checks) / len(white_core_checks)

    activation_confidence = max(bright_confidence, white_confidence)

    if is_on:
        confidence = (green_confidence + activation_confidence) / 2.0
    else:
        # Für OFF soll Confidence zeigen, wie sicher "nicht aktiv" erkannt wurde.
        # Grün allein zählt hier nicht als ON-Nähe, weil die LED-Kappe auch ausgeschaltet grün ist.
        confidence = 1.0 - activation_confidence

    confidence = max(0.0, min(1.0, confidence))

    return (1 if is_on else 0), confidence