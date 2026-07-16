"""Noise-resistant detection of a device consistently moving away."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class DepartureTrend:
    triggered: bool = False
    confidence: float = 0.0
    progress: float = 0.0
    duration: float = 0.0
    slope_db_per_second: float = 0.0
    rssi_drop: float = 0.0
    consistency: float = 0.0
    sample_count: int = 0


class DepartureTrendDetector:
    """Detect sustained RSSI decline over a configurable time window.

    A falling RSSI corresponds to increasing estimated distance. Linear
    regression and a consistency score make the detector tolerant of normal
    BLE jitter while rejecting isolated signal drops.
    """

    def __init__(
        self,
        window_seconds: float,
        min_samples: int = 6,
        min_rssi_drop: float = 4.0,
        min_slope_db_per_second: float = 0.8,
        min_consistency: float = 0.72,
        noise_tolerance_db: float = 0.8,
    ):
        self.window_seconds = max(1.0, float(window_seconds))
        self.min_samples = max(3, int(min_samples))
        self.min_rssi_drop = float(min_rssi_drop)
        self.min_slope = float(min_slope_db_per_second)
        self.min_consistency = float(min_consistency)
        self.noise_tolerance = float(noise_tolerance_db)
        self._samples: deque[tuple[float, float]] = deque()

    def reset(self):
        self._samples.clear()

    def add(self, rssi: float, timestamp: float | None = None) -> DepartureTrend:
        now = time.monotonic() if timestamp is None else float(timestamp)
        self._samples.append((now, float(rssi)))
        cutoff = now - self.window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        return self._evaluate()

    def _evaluate(self) -> DepartureTrend:
        count = len(self._samples)
        if count < 2:
            return DepartureTrend(sample_count=count)

        times = [sample[0] for sample in self._samples]
        values = [sample[1] for sample in self._samples]
        duration = max(0.0, times[-1] - times[0])
        progress = min(1.0, duration / self.window_seconds)

        mean_t = sum(times) / count
        mean_rssi = sum(values) / count
        variance_t = sum((value - mean_t) ** 2 for value in times)
        slope = 0.0
        if variance_t > 0:
            slope = sum(
                (timestamp - mean_t) * (rssi - mean_rssi)
                for timestamp, rssi in self._samples
            ) / variance_t

        edge_size = max(1, count // 4)
        start_average = sum(values[:edge_size]) / edge_size
        end_average = sum(values[-edge_size:]) / edge_size
        rssi_drop = start_average - end_average

        deltas = [current - previous for previous, current in zip(values, values[1:])]
        consistent_steps = sum(delta <= self.noise_tolerance for delta in deltas)
        consistency = consistent_steps / len(deltas) if deltas else 0.0

        duration_score = progress
        drop_score = max(0.0, min(1.0, rssi_drop / self.min_rssi_drop))
        slope_score = max(0.0, min(1.0, -slope / self.min_slope))
        consistency_score = max(0.0, min(1.0, consistency / self.min_consistency))
        confidence = min(duration_score, drop_score, slope_score, consistency_score)

        triggered = (
            count >= self.min_samples
            and progress >= 0.9
            and rssi_drop >= self.min_rssi_drop
            and slope <= -self.min_slope
            and consistency >= self.min_consistency
        )
        return DepartureTrend(
            triggered=triggered,
            confidence=confidence,
            progress=progress,
            duration=duration,
            slope_db_per_second=slope,
            rssi_drop=rssi_drop,
            consistency=consistency,
            sample_count=count,
        )

