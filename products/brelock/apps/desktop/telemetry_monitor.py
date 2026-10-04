"""Observe one keyfob using monotonic time. No OS actions or network services."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import math
from statistics import median

from telemetry_protocol import TelemetryPacket


@dataclass(frozen=True)
class MonitorConfig:
    reference_rssi_dbm: float = -59.0
    path_loss_exponent: float = 2.2
    bucket_seconds: float = 0.25
    median_seconds: float = 0.75
    ema_tau_seconds: float = 0.8
    trend_seconds: float = 3.0
    fresh_seconds: float = 1.5
    lost_seconds: float = 6.0

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not math.isfinite(value):
                raise ValueError(f"{name}: wymagana skończona liczba")
            if name != "reference_rssi_dbm" and value <= 0:
                raise ValueError(f"{name}: wymagana dodatnia liczba")
        if self.lost_seconds <= self.fresh_seconds:
            raise ValueError("lost_seconds musi być większe niż fresh_seconds")


class SignalFilter:
    """At most one filter update per time bucket, irrespective of callbacks."""

    def __init__(self, config: MonitorConfig):
        self.config = config
        self.bucket: int | None = None
        self.samples: deque[float] = deque(maxlen=64)
        self.bins: deque[tuple[float, float]] = deque()
        self.points: deque[tuple[float, float]] = deque()
        self.ema: float | None = None
        self.ema_at: float | None = None

    def advance(self, at: float) -> None:
        if self.bucket is not None and at >= (self.bucket + 1) * self.config.bucket_seconds:
            end = (self.bucket + 1) * self.config.bucket_seconds
            self._finish(end)
            self.bucket = None
            self.samples.clear()
        while self.points and self.points[0][0] < at - self.config.trend_seconds:
            self.points.popleft()

    def add(self, at: float, rssi: float) -> None:
        self.advance(at)
        bucket = math.floor(at / self.config.bucket_seconds)
        if self.bucket is not None and bucket < self.bucket:
            return
        self.bucket = bucket
        self.samples.append(rssi)

    def _finish(self, at: float) -> None:
        if not self.samples:
            return
        self.bins.append((at, median(self.samples)))
        while self.bins and self.bins[0][0] <= at - self.config.median_seconds:
            self.bins.popleft()
        if len(self.bins) < 2:
            return
        value = median([value for _, value in self.bins])
        if self.ema is None:
            self.ema = value
        else:
            dt = at - self.ema_at
            alpha = -math.expm1(-dt / self.config.ema_tau_seconds)
            self.ema += alpha * (value - self.ema)
        self.ema_at = at
        self.points.append((at, self.ema))

    def trend(self) -> dict:
        points = list(self.points)
        result = {"quality": "warming_up", "points": len(points), "span_s": 0.0,
                  "coverage": 0.0, "slope_db_s": None, "r_squared": None,
                  "residual_std_db": None}
        if len(points) < 2:
            return result
        span = points[-1][0] - points[0][0]
        coverage = min(1.0, len(points) / (self.config.trend_seconds / self.config.bucket_seconds))
        result.update(span_s=span, coverage=coverage)
        if len(points) < 6 or span < 0.8 * self.config.trend_seconds - 1e-9:
            return result
        if coverage < 0.8:
            result["quality"] = "gaps"
            return result
        # Subtract the first timestamp before fitting: large monotonic values
        # must not degrade the regression's numerical precision.
        xs = [at - points[0][0] for at, _ in points]
        ys = [value for _, value in points]
        x_mean, y_mean = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - x_mean) ** 2 for x in xs)
        syy = sum((y - y_mean) ** 2 for y in ys)
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sxx
        residual = sum((y - y_mean - slope * (x - x_mean)) ** 2 for x, y in zip(xs, ys))
        r_squared = max(0.0, min(1.0, 1.0 - residual / syy)) if syy > 1e-12 else None
        result.update(slope_db_s=slope, r_squared=r_squared,
                      residual_std_db=math.sqrt(residual / len(xs)),
                      quality="valid" if r_squared is not None and r_squared >= 0.5 else "no_clear_trend")
        return result


class DeviceMonitor:
    def __init__(self, device_id: str, config: MonitorConfig | None = None):
        self.device_id = device_id
        self.config = config or MonitorConfig()
        self.packet: TelemetryPacket | None = None
        self.name: str | None = None
        self.address = ""
        self.last_packet_at: float | None = None
        self.last_callback_at: float | None = None
        self.last_rssi_at: float | None = None
        self.last_rssi: float | None = None
        self.signal = SignalFilter(self.config)
        self.retired_boots: deque[int] = deque(maxlen=16)
        self.new_times: deque[float] = deque()
        self.callback_times: deque[float] = deque()
        self.started_at: float | None = None
        self.counts = dict(callbacks=0, new_packets=0, duplicates=0, out_of_order=0,
                           conflicting_duplicates=0, skipped_summaries=0,
                           reboots=0, signal_resets=0, invalid_rssi=0)

    def receive(self, packet: TelemetryPacket, rssi: float | None, at: float,
                address: str = "", name: str | None = None) -> str:
        if packet.device_id != self.device_id:
            return "foreign"
        self.name = name or self.name
        self.address = address or self.address
        self.counts["callbacks"] += 1
        self.last_callback_at = at
        self.callback_times.append(at)
        self._prune(self.callback_times, at)
        if self.started_at is None:
            self.started_at = at
        previous = self.packet
        disposition = "new"
        if previous is not None and packet.protocol_version == previous.protocol_version == 2:
            if packet.boot_id != previous.boot_id:
                if packet.boot_id in self.retired_boots:
                    self.counts["out_of_order"] += 1
                    return "old_boot"
                self.retired_boots.append(previous.boot_id)
                self.counts["reboots"] += 1
                disposition = "reboot"
                self._reset_signal()
            else:
                delta = (packet.sequence - previous.sequence) & 0xFFFFFFFF
                if delta == 0:
                    if packet != previous:
                        self.counts["conflicting_duplicates"] += 1
                        return "conflict"
                    self.counts["duplicates"] += 1
                    if at - self.last_packet_at <= self.config.fresh_seconds:
                        self._add_rssi(rssi, at)
                    return "duplicate"
                if delta >= 0x80000000:
                    self.counts["out_of_order"] += 1
                    return "out_of_order"
                self.counts["skipped_summaries"] += delta - 1
        # Do not fit across a radio interruption, reboot, or protocol change.
        if previous is not None and disposition != "reboot" and (
                at - self.last_packet_at > self.config.fresh_seconds
                or packet.protocol_version != previous.protocol_version):
            self._reset_signal()
        self.packet = packet
        self.last_packet_at = at
        self.counts["new_packets"] += 1
        self.new_times.append(at)
        self._prune(self.new_times, at)
        self._add_rssi(rssi, at)
        return "legacy_callback" if packet.protocol_version == 1 else disposition

    def _reset_signal(self) -> None:
        self.signal = SignalFilter(self.config)
        self.last_rssi_at = None
        self.last_rssi = None
        self.counts["signal_resets"] += 1

    def _add_rssi(self, rssi: float | None, at: float) -> None:
        if rssi is None or not math.isfinite(rssi) or not -127 <= rssi <= 20:
            self.counts["invalid_rssi"] += 1
            return
        if self.last_rssi_at is not None and at - self.last_rssi_at > self.config.fresh_seconds:
            self._reset_signal()
        self.last_rssi, self.last_rssi_at = float(rssi), at
        self.signal.add(at, float(rssi))

    @staticmethod
    def _prune(times: deque[float], at: float) -> None:
        while times and times[0] < at - 5.0:
            times.popleft()

    def _rate(self, times: deque[float], at: float) -> float | None:
        self._prune(times, at)
        duration = at - self.started_at if self.started_at is not None else 0
        return len(times) / min(5.0, duration) if duration >= 1.0 else None

    def snapshot(self, at: float) -> dict:
        self.signal.advance(at)
        packet = self.packet
        age = at - self.last_packet_at if self.last_packet_at is not None else None
        radio_fresh = age is not None and age <= self.config.fresh_seconds
        fresh = radio_fresh and packet.protocol_version == 2
        status = ("WAITING" if packet is None else "LOST" if age >= self.config.lost_seconds
                  else "STALE" if not radio_fresh else "LIVE" if fresh else "LEGACY")
        signal_fresh = (radio_fresh and self.last_rssi_at is not None
                        and at - self.last_rssi_at <= self.config.fresh_seconds)
        filtered = self.signal.ema if signal_fresh else None
        distance = None
        if filtered is not None:
            try:
                distance = 10.0 ** ((self.config.reference_rssi_dbm - filtered)
                                    / (10.0 * self.config.path_loss_exponent))
                if not math.isfinite(distance) or distance <= 0:
                    distance = None
            except OverflowError:
                pass
        trend = self.signal.trend()
        if not signal_fresh:
            trend.update(quality="stale", slope_db_s=None, r_squared=None, residual_std_db=None)
        speed = None
        if distance is not None and trend["quality"] == "valid":
            # A derivative of the RSSI distance model; NOT integrated IMU speed.
            speed = -math.log(10) * distance * trend["slope_db_s"] / (10 * self.config.path_loss_exponent)
            if not math.isfinite(speed):
                speed = None
        imu_valid = bool(fresh and packet.imu_valid)
        gyro_valid = bool(imu_valid and packet.gyro_valid)
        motion_age = (packet.motion_age_ms / 1000.0 + age
                      if imu_valid and packet.motion_age_ms is not None else None)
        acc = packet.acceleration_rms_mg if imu_valid else None
        battery = packet.battery_mv if fresh and packet.battery_valid else None
        return {
            "device_id": self.device_id, "name": self.name, "address": self.address,
            "protocol_version": packet.protocol_version if packet else None,
            "status": status, "telemetry_fresh": fresh, "radio_fresh": radio_fresh,
            "packet_age_s": age,
            "callback_age_s": at - self.last_callback_at if self.last_callback_at is not None else None,
            "rssi_raw_dbm": self.last_rssi if signal_fresh else None,
            "rssi_last_dbm": self.last_rssi,
            "rssi_filtered_dbm": filtered, "distance_estimate_m": distance,
            "radial_speed_estimate_m_s": speed, "actual_speed_m_s": None,
            "trend": trend, "imu_valid": imu_valid, "gyro_valid": gyro_valid,
            "motion": ("moving" if packet.moving else "still") if imu_valid else "unknown",
            "motion_age_s": motion_age,
            "motion_age_saturated": bool(imu_valid and packet.motion_age_saturated),
            "recent_motion": motion_age <= 5.0 if motion_age is not None else None,
            "acceleration_rms_mg": acc,
            "acceleration_rms_m_s2": acc * 9.80665 / 1000.0 if acc is not None else None,
            "gyro_rms_dps": packet.gyro_rms_dps if gyro_valid else None,
            "battery_mv": battery, "battery_low": battery < 3500 if battery is not None else None,
            "clipped": packet.clipped if fresh else None,
            "nominal_tx_dbm": packet.nominal_tx_dbm if packet else None,
            "packet_hz": self._rate(self.new_times, at) if packet and packet.protocol_version == 2 else None,
            "callback_hz": self._rate(self.callback_times, at), "counters": dict(self.counts),
            "last_packet": packet.to_dict() if packet else None,
        }
