"""The firmware's manufacturer payload, without the two-byte company ID."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import struct

COMPANY_ID = 0xFFFF
SERVICE_UUID = "9e20a100-6f7f-4d8a-9c21-4b52454c4f43"
V2_PAYLOAD = struct.Struct("<BB6sHIBHHHHb")
V3_PAYLOAD = struct.Struct("<BB6sHIBHHHHB")
UNKNOWN_MOTION_AGE = 0xFFFF
SATURATED_MOTION_AGE = 0xFFFE


class PacketError(ValueError):
    """A claimed breLock packet does not match its wire format."""


@dataclass(frozen=True)
class TelemetryPacket:
    device_id: str
    protocol_version: int
    boot_id: int | None = None
    sequence: int | None = None
    flags: int = 0
    imu_valid: bool = False
    gyro_valid: bool = False
    clipped: bool = False
    battery_valid: bool = False
    moving: bool | None = None
    acceleration_rms_mg: int | None = None
    gyro_rms_dps: float | None = None
    motion_age_ms: int | None = None
    motion_age_saturated: bool = False
    battery_mv: int | None = None
    nominal_tx_dbm: int | None = None
    button_event_active: bool = False
    button_event_count: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_device_id(value: str) -> str:
    """Hardware ID, not the platform's BLE address/UUID or advertised name."""
    normalized = value.replace(":", "").replace("-", "").upper()
    if not re.fullmatch(r"[0-9A-F]{12}", normalized):
        raise ValueError("ID breloka musi mieć 12 znaków hex, np. A1B2C3D4E5F6")
    return normalized


def decode_telemetry(payload: bytes) -> TelemetryPacket | None:
    """Ignore foreign/unknown versions; reject malformed supported packets.

    v1 is useful for radio diagnostics, but has no IMU or freshness counter.
    Invalid sensor fields become None rather than a false zero measurement.
    """
    if len(payload) < 2 or payload[0] not in (1, 2, 3) or payload[1] != 1:
        return None
    version = payload[0]
    expected = 8 if version == 1 else (V2_PAYLOAD.size if version == 2 else V3_PAYLOAD.size)
    if len(payload) != expected:
        raise PacketError(f"BLE v{version}: {len(payload)} B zamiast {expected} B")
    if version == 1:
        return TelemetryPacket(payload[2:8].hex().upper(), 1)

    if version == 2:
        (_, _, identifier, boot, sequence, flags, acc, gyro, age, battery, tx) = (
            V2_PAYLOAD.unpack(payload)
        )
        button_count = None
        button_active = False
    else:
        (_, _, identifier, boot, sequence, flags, acc, gyro, age, battery, button_count) = (
            V3_PAYLOAD.unpack(payload)
        )
        tx = 3
        button_active = bool(flags & (1 << 5))
    moving, imu_valid, gyro_valid, clipped, battery_valid = (
        bool(flags & (1 << bit)) for bit in range(5)
    )
    if flags & (0xE0 if version == 2 else 0xC0):
        raise PacketError(f"BLE v{version}: ustawione zarezerwowane flagi")
    if ((moving or gyro_valid) and not imu_valid) or (clipped and imu_valid):
        raise PacketError("BLE v2: niespójne flagi ruchu/IMU/gyro/clipping")
    if not imu_valid and (acc or age != UNKNOWN_MOTION_AGE):
        raise PacketError("BLE v2: nieważne IMU musi mieć RMS=0 i nieznany wiek ruchu")
    if not gyro_valid and gyro:
        raise PacketError("BLE v2: nieważny gyro musi mieć RMS=0")
    if (not battery_valid and battery) or (battery_valid and not 2500 <= battery <= 4500):
        raise PacketError("BLE v2: niespójne napięcie/flaga baterii")

    return TelemetryPacket(
        device_id=identifier.hex().upper(), protocol_version=version,
        boot_id=boot, sequence=sequence, flags=flags,
        imu_valid=imu_valid, gyro_valid=gyro_valid, clipped=clipped,
        battery_valid=battery_valid, moving=moving if imu_valid else None,
        acceleration_rms_mg=acc if imu_valid else None,
        gyro_rms_dps=gyro / 10.0 if gyro_valid else None,
        motion_age_ms=age if imu_valid and age != UNKNOWN_MOTION_AGE else None,
        motion_age_saturated=imu_valid and age == SATURATED_MOTION_AGE,
        battery_mv=battery if battery_valid else None, nominal_tx_dbm=tx,
        button_event_active=button_active, button_event_count=button_count,
    )
