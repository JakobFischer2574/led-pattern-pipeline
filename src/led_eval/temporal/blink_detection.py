from __future__ import annotations


def classify_led_temporal_state(values: list[int], fps: float = 1.0) -> str:
    known = [v for v in values if v in {0, 1}]
    if not known:
        return "unknown"
    on_ratio = sum(known) / len(known)
    transitions = sum(1 for a, b in zip(known, known[1:]) if a != b)
    transition_rate = transitions / max(len(known) / max(fps, 0.001), 0.001)

    if on_ratio >= 0.85 and transitions <= 1:
        return "on"
    if on_ratio <= 0.15 and transitions <= 1:
        return "off"
    if transitions < 2:
        return "unknown"
    if transition_rate >= 0.7:
        return "blink_fast"
    return "blink_slow"


def classify_video_pattern(led_sequences: list[list[int]], fps: float = 1.0) -> dict[str, str]:
    return {
        f"led_{index}": classify_led_temporal_state(sequence, fps=fps)
        for index, sequence in enumerate(led_sequences, start=1)
    }
