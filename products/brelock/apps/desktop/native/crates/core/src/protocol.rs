use serde::{Deserialize, Serialize};
use std::{fmt, str::FromStr};
use thiserror::Error;

pub const COMPANY_ID: u16 = 0xffff;
pub const SERVICE_UUID: &str = "9e20a100-6f7f-4d8a-9c21-4b52454c4f43";
pub const PAYLOAD_SIZE: usize = 24;
pub const PREVIOUS_PROTOCOL_VERSION: u8 = 2;
pub const PROTOCOL_VERSION: u8 = 3;
pub const UNKNOWN_MOTION_AGE: u16 = 0xffff;
pub const SATURATED_MOTION_AGE: u16 = 0xfffe;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct DeviceId([u8; 6]);

impl DeviceId {
    pub const fn from_bytes(bytes: [u8; 6]) -> Self {
        Self(bytes)
    }
    pub const fn bytes(self) -> [u8; 6] {
        self.0
    }
}

impl fmt::Display for DeviceId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in self.0 {
            write!(f, "{byte:02X}")?;
        }
        Ok(())
    }
}

impl FromStr for DeviceId {
    type Err = ProtocolError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let value = value.replace([':', '-'], "");
        if value.len() != 12 || !value.bytes().all(|byte| byte.is_ascii_hexdigit()) {
            return Err(ProtocolError::InvalidId);
        }
        let mut bytes = [0u8; 6];
        for (index, byte) in bytes.iter_mut().enumerate() {
            *byte = u8::from_str_radix(&value[index * 2..index * 2 + 2], 16)
                .map_err(|_| ProtocolError::InvalidId)?;
        }
        Ok(Self(bytes))
    }
}

impl TryFrom<String> for DeviceId {
    type Error = ProtocolError;
    fn try_from(value: String) -> Result<Self, Self::Error> {
        value.parse()
    }
}

impl From<DeviceId> for String {
    fn from(value: DeviceId) -> Self {
        value.to_string()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TelemetryPacket {
    pub device_id: DeviceId,
    pub protocol_version: u8,
    pub boot_id: u16,
    pub sequence: u32,
    pub flags: u8,
    pub imu_valid: bool,
    pub gyro_valid: bool,
    pub clipped: bool,
    pub battery_valid: bool,
    pub moving: Option<bool>,
    pub acceleration_rms_mg: Option<u16>,
    pub gyro_rms_dps: Option<f64>,
    pub motion_age_ms: Option<u16>,
    pub motion_age_saturated: bool,
    pub battery_mv: Option<u16>,
    pub nominal_tx_dbm: i8,
    pub button_event_active: bool,
    pub button_event_count: Option<u8>,
}

#[derive(Debug, Error)]
pub enum ProtocolError {
    #[error("hardware ID must contain 12 hex digits")]
    InvalidId,
    #[error("BLE v2 requires 24 payload bytes, got {0}")]
    InvalidLength(usize),
    #[error("unsupported protocol or device type")]
    Unsupported,
    #[error("inconsistent or reserved telemetry flags")]
    InvalidFlags,
    #[error("invalid sensor values must contain zero RMS and unknown motion age")]
    InvalidSensor,
    #[error("inconsistent battery value/validity flag")]
    InvalidBattery,
    #[error("payload hex must contain complete hexadecimal byte pairs")]
    InvalidHex,
}

pub fn decode_hex(value: &str) -> Result<Vec<u8>, ProtocolError> {
    let value: String = value.chars().filter(|c| !c.is_whitespace()).collect();
    if !value.len().is_multiple_of(2) || !value.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(ProtocolError::InvalidHex);
    }
    (0..value.len())
        .step_by(2)
        .map(|index| {
            u8::from_str_radix(&value[index..index + 2], 16).map_err(|_| ProtocolError::InvalidHex)
        })
        .collect()
}

pub fn payload_hex(payload: &[u8]) -> String {
    payload.iter().map(|byte| format!("{byte:02X}")).collect()
}

/// Decode manufacturer data AFTER the two-byte company ID, as provided by btleplug.
/// v2 remains accepted; v3 adds a touch marker in flag 5 and byte 23.
pub fn decode_telemetry(payload: &[u8]) -> Result<TelemetryPacket, ProtocolError> {
    if payload.len() != PAYLOAD_SIZE {
        return Err(ProtocolError::InvalidLength(payload.len()));
    }
    let version = payload[0];
    if !matches!(version, PREVIOUS_PROTOCOL_VERSION | PROTOCOL_VERSION) || payload[1] != 1 {
        return Err(ProtocolError::Unsupported);
    }
    let u16_at = |offset| u16::from_le_bytes([payload[offset], payload[offset + 1]]);
    let flags = payload[14];
    let event_flags = if version == PROTOCOL_VERSION {
        0xc0
    } else {
        0xe0
    };
    let moving = flags & 1 != 0;
    let imu_valid = flags & 2 != 0;
    let gyro_valid = flags & 4 != 0;
    let clipped = flags & 8 != 0;
    let battery_valid = flags & 16 != 0;
    if flags & event_flags != 0 || ((moving || gyro_valid) && !imu_valid) || (clipped && imu_valid)
    {
        return Err(ProtocolError::InvalidFlags);
    }
    let acc = u16_at(15);
    let gyro = u16_at(17);
    let age = u16_at(19);
    let battery = u16_at(21);
    if (!imu_valid && (acc != 0 || age != UNKNOWN_MOTION_AGE)) || (!gyro_valid && gyro != 0) {
        return Err(ProtocolError::InvalidSensor);
    }
    if (!battery_valid && battery != 0) || (battery_valid && !(2500..=4500).contains(&battery)) {
        return Err(ProtocolError::InvalidBattery);
    }
    Ok(TelemetryPacket {
        device_id: DeviceId::from_bytes([
            payload[2], payload[3], payload[4], payload[5], payload[6], payload[7],
        ]),
        protocol_version: version,
        boot_id: u16_at(8),
        sequence: u32::from_le_bytes([payload[10], payload[11], payload[12], payload[13]]),
        flags,
        imu_valid,
        gyro_valid,
        clipped,
        battery_valid,
        moving: imu_valid.then_some(moving),
        acceleration_rms_mg: imu_valid.then_some(acc),
        gyro_rms_dps: gyro_valid.then_some(f64::from(gyro) / 10.0),
        motion_age_ms: (imu_valid && age != UNKNOWN_MOTION_AGE).then_some(age),
        motion_age_saturated: imu_valid && age == SATURATED_MOTION_AGE,
        battery_mv: battery_valid.then_some(battery),
        nominal_tx_dbm: if version == PREVIOUS_PROTOCOL_VERSION {
            payload[23] as i8
        } else {
            // v3 repurposes this legacy diagnostic byte as a touch event counter.
            3
        },
        button_event_active: version == PROTOCOL_VERSION && flags & (1 << 5) != 0,
        button_event_count: (version == PROTOCOL_VERSION).then_some(payload[23]),
    })
}
