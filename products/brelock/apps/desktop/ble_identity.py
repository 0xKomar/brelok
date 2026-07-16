from __future__ import annotations

from dataclasses import dataclass


BRELOCK_COMPANY_ID = 0xFFFF
BRELOCK_PROTOCOL_VERSION = 1
BRELOCK_DEVICE_TYPE_KEYFOB = 1


@dataclass(frozen=True)
class BrelockIdentity:
    device_id: str
    protocol_version: int
    device_type: int


def decode_brelock_identity(advertisement_data) -> BrelockIdentity | None:
    """Decode the full hardware ID from Bleak manufacturer data."""
    manufacturer_data = getattr(advertisement_data, "manufacturer_data", {}) or {}
    payload = manufacturer_data.get(BRELOCK_COMPANY_ID)
    if payload is None or len(payload) < 8:
        return None
    version, device_type = payload[0], payload[1]
    if version != BRELOCK_PROTOCOL_VERSION or device_type != BRELOCK_DEVICE_TYPE_KEYFOB:
        return None
    return BrelockIdentity(
        device_id=bytes(payload[2:8]).hex().upper(),
        protocol_version=version,
        device_type=device_type,
    )

