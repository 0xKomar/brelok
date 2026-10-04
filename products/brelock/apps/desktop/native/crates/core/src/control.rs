//! Small GATT messages shared with the fob. Actions are scoped to one live
//! desktop session and consumed once, including after reconnects.
use crate::DeviceId;
use serde::Serialize;
use thiserror::Error;

pub const TELEMETRY_UUID: &str = "9e20a101-6f7f-4d8a-9c21-4b52454c4f43";
pub const HOST_STATUS_UUID: &str = "9e20a102-6f7f-4d8a-9c21-4b52454c4f43";
pub const COMMAND_UUID: &str = "9e20a103-6f7f-4d8a-9c21-4b52454c4f43";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
#[repr(u8)]
pub enum DeviceAction {
    StartCalibration = 1,
    SaveCalibration = 2,
    LockNow = 3,
    CancelCalibration = 4,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct ControlRequest {
    pub action: DeviceAction,
    pub sequence: u16,
    pub session: u64,
}

#[derive(Debug, Error)]
#[error("invalid GATT control message")]
pub struct ControlError;

impl ControlRequest {
    pub fn decode(bytes: &[u8]) -> Result<Self, ControlError> {
        if bytes.len() != 12 || bytes[0] != 1 {
            return Err(ControlError);
        }
        let action = match bytes[1] {
            1 => DeviceAction::StartCalibration,
            2 => DeviceAction::SaveCalibration,
            3 => DeviceAction::LockNow,
            4 => DeviceAction::CancelCalibration,
            _ => return Err(ControlError),
        };
        let sequence = u16::from_le_bytes([bytes[2], bytes[3]]);
        let session = u64::from_le_bytes(bytes[4..12].try_into().unwrap());
        if sequence == 0 || session == 0 {
            return Err(ControlError);
        }
        Ok(Self {
            action,
            sequence,
            session,
        })
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct HostStatus {
    pub protection: u8,
    pub flags: u8,
    pub calibration: u8,
    pub feedback: u8,
    pub calibration_percent: u8,
    /// Guided point 1..=3; zero preserves the original single-point wire format.
    pub calibration_step: u8,
    pub movement_seconds: u8,
    pub rssi_dbm: Option<i8>,
    pub distance_cm: Option<u16>,
    pub acknowledged_sequence: u16,
    pub session: u64,
}

impl HostStatus {
    pub fn encode(self) -> [u8; 20] {
        let mut bytes = [0u8; 20];
        bytes[0] = if self.calibration_step == 0 { 1 } else { 2 };
        bytes[1] = self.protection;
        bytes[2] = self.flags;
        bytes[3] = self.calibration;
        bytes[4] = self.feedback;
        bytes[5] = self.calibration_percent;
        bytes[6] = self.rssi_dbm.unwrap_or(i8::MIN) as u8;
        bytes[7] = (self.calibration_step & 15) | ((self.movement_seconds & 15) << 4);
        bytes[8..10].copy_from_slice(&self.distance_cm.unwrap_or(u16::MAX).to_le_bytes());
        bytes[10..12].copy_from_slice(&self.acknowledged_sequence.to_le_bytes());
        bytes[12..20].copy_from_slice(&self.session.to_le_bytes());
        bytes
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct HostUpdate {
    pub device_id: Option<DeviceId>,
    pub status: HostStatus,
}

#[derive(Debug, Default)]
pub struct ControlGate {
    pub session: u64,
    last_sequence: Option<u16>,
}

impl ControlGate {
    pub fn new(session: u64) -> Self {
        Self {
            session,
            last_sequence: None,
        }
    }
    pub fn accept(&mut self, request: ControlRequest) -> bool {
        if request.session != self.session || self.session == 0 {
            return false;
        }
        if let Some(previous) = self.last_sequence {
            let advance = request.sequence.wrapping_sub(previous);
            if advance == 0 || advance >= 0x8000 {
                return false;
            }
        }
        self.last_sequence = Some(request.sequence);
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wire_bytes_match_firmware_and_reject_malformed_actions() {
        let bytes = [1, 3, 7, 0, 8, 7, 6, 5, 4, 3, 2, 1];
        let command = ControlRequest::decode(&bytes).unwrap();
        assert_eq!(command.action, DeviceAction::LockNow);
        assert_eq!(command.session, 0x0102030405060708);
        let status = HostStatus {
            protection: 1,
            flags: 7,
            calibration: 2,
            feedback: 3,
            calibration_percent: 100,
            rssi_dbm: Some(-61),
            distance_cm: Some(250),
            acknowledged_sequence: 7,
            session: command.session,
            ..HostStatus::default()
        }
        .encode();
        assert_eq!(&status[..12], &[1, 1, 7, 2, 3, 100, 195, 0, 250, 0, 7, 0]);
        assert_eq!(&status[12..], &bytes[4..]);
        assert!(ControlRequest::decode(&[0; 12]).is_err());
        assert!(ControlRequest::decode(&bytes[..11]).is_err());
        let mut invalid = bytes;
        invalid[1] = 9;
        assert!(ControlRequest::decode(&invalid).is_err());
    }
    #[test]
    fn actions_are_one_shot_and_cannot_cross_host_sessions() {
        let mut gate = ControlGate::new(55);
        let mut request = ControlRequest {
            action: DeviceAction::LockNow,
            sequence: 65535,
            session: 55,
        };
        assert!(gate.accept(request));
        assert!(!gate.accept(request));
        request.sequence = 1;
        assert!(gate.accept(request));
        request.sequence = 65535;
        assert!(!gate.accept(request));
        request.session = 56;
        request.sequence = 2;
        assert!(!gate.accept(request));
    }

    #[test]
    fn guided_status_fits_in_twenty_bytes_and_preserves_session_and_ack() {
        let status = HostStatus {
            calibration: 5,
            calibration_step: 2,
            movement_seconds: 2,
            acknowledged_sequence: 4097,
            session: 0x0102030405060708,
            ..HostStatus::default()
        }
        .encode();
        assert_eq!(&status[..8], &[2, 0, 0, 5, 0, 0, 128, 0x22]);
        assert_eq!(&status[10..12], &[1, 16]);
        assert_eq!(&status[12..], &[8, 7, 6, 5, 4, 3, 2, 1]);
        assert_eq!(HostStatus::default().encode()[0], 1);
    }

    #[test]
    fn reconnect_accepts_a_reset_counter_only_in_the_new_session() {
        let previous = ControlRequest {
            action: DeviceAction::StartCalibration,
            sequence: 5,
            session: 55,
        };
        let mut gate = ControlGate::new(55);
        assert!(gate.accept(previous));
        gate = ControlGate::new(56);
        assert!(!gate.accept(previous));
        let next = ControlRequest {
            sequence: 1,
            session: 56,
            ..previous
        };
        assert!(gate.accept(next));
        assert!(!gate.accept(next));
    }
}
