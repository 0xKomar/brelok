use crate::protocol::DeviceId;
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct AppConfig {
    pub schema_version: u32,
    pub device_id: Option<DeviceId>,
    pub reference_rssi_dbm: f64,
    pub path_loss_exponent: f64,
    /// Physical distance of the saved boundary (3 m after the guided series).
    pub calibration_distance_m: f64,
    /// RSSI boundary learned by calibration. None uses START thresholds.
    pub departure_threshold_dbm: Option<f64>,
    /// Continuous confirmation time for RSSI-based departure rules.
    pub departure_confirm_seconds: f64,
    pub fresh_seconds: f64,
    pub lost_seconds: f64,
    pub refresh_hz: f64,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            schema_version: 1,
            device_id: None,
            reference_rssi_dbm: -59.0,
            path_loss_exponent: 2.2,
            calibration_distance_m: 3.0,
            departure_threshold_dbm: None,
            departure_confirm_seconds: 0.7,
            fresh_seconds: 1.5,
            lost_seconds: 3.0,
            refresh_hz: 5.0,
        }
    }
}

#[derive(Debug, Error)]
#[error("invalid configuration: {0}")]
pub struct ConfigError(pub &'static str);

impl AppConfig {
    pub fn validate(&self) -> Result<(), ConfigError> {
        if self.schema_version != 1 {
            return Err(ConfigError("unsupported schema_version"));
        }
        if !self.reference_rssi_dbm.is_finite() {
            return Err(ConfigError("reference_rssi_dbm must be finite"));
        }
        if !self.calibration_distance_m.is_finite()
            || !(0.5..=20.0).contains(&self.calibration_distance_m)
        {
            return Err(ConfigError("calibration_distance_m must be in 0.5..=20 m"));
        }
        if self
            .departure_threshold_dbm
            .is_some_and(|value| !value.is_finite() || !(-110.0..=-35.0).contains(&value))
        {
            return Err(ConfigError(
                "departure_threshold_dbm must be finite and in -110..=-35 dBm",
            ));
        }
        for value in [
            self.path_loss_exponent,
            self.departure_confirm_seconds,
            self.fresh_seconds,
            self.lost_seconds,
        ] {
            if !value.is_finite() || value <= 0.0 {
                return Err(ConfigError(
                    "model and timing parameters must be finite and positive",
                ));
            }
        }
        if self.lost_seconds <= self.fresh_seconds {
            return Err(ConfigError(
                "lost_seconds must be greater than fresh_seconds",
            ));
        }
        if !(0.5..=5.0).contains(&self.departure_confirm_seconds) {
            return Err(ConfigError(
                "departure_confirm_seconds must be in 0.5..=5 seconds",
            ));
        }
        if !self.refresh_hz.is_finite() || !(0.2..=20.0).contains(&self.refresh_hz) {
            return Err(ConfigError("refresh_hz must be in 0.2..=20"));
        }
        Ok(())
    }
}
