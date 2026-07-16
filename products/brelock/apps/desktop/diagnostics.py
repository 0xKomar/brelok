"""Pure helpers used by the live BLE diagnostics UI."""

from __future__ import annotations

import math


def estimate_distance(
    rssi: float,
    reference_rssi: float = -59.0,
    path_loss_exponent: float = 2.2,
) -> float:
    """Estimate distance in metres from RSSI using a log-distance model.

    RSSI is inherently noisy, so this value is diagnostic rather than a precise
    physical measurement. ``reference_rssi`` should be measured at one metre.
    """
    if path_loss_exponent <= 0:
        raise ValueError("path_loss_exponent must be positive")

    distance = 10 ** ((reference_rssi - float(rssi)) / (10 * path_loss_exponent))
    return max(0.05, min(50.0, distance))


def signal_quality(rssi: float) -> int:
    """Map the useful BLE range (-100..-40 dBm) to a 0..100 score."""
    return max(0, min(100, round((float(rssi) + 100) / 60 * 100)))


def format_distance(distance: float) -> str:
    if not math.isfinite(distance):
        return "—"
    if distance < 1:
        return f"{round(distance * 100):d} cm"
    return f"{distance:.1f} m"

