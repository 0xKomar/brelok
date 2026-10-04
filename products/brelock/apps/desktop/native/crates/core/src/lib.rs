//! Platform-independent domain types. Time is supplied by the caller.
//! No Bluetooth, file access, GUI, or OS actions in this crate.

pub mod config;
pub mod control;
pub mod monitor;
pub mod protection;
pub mod protocol;
pub mod signal;

pub use config::AppConfig;
pub use monitor::{DeviceMonitor, DeviceSnapshot, Observation, ReceiveDisposition};
pub use protection::{
    LockAttemptStatus, ProtectionEngine, ProtectionSnapshot, ProtectionState, TripReason,
};
pub use protocol::{DeviceId, TelemetryPacket, decode_telemetry};
