//! Fail-safe, opt-in away-detection rules for one selected key fob.
//! Time is supplied by the caller so the evaluator is independent of UI/OS.

use crate::{
    monitor::{ConnectionState, DeviceSnapshot},
    signal::TrendQuality,
};
use serde::Serialize;
use std::time::Duration;

pub const HARD_FAR_DBM: f64 = -80.0;
pub const FAR_DBM: f64 = -72.0;
pub const FAST_FAR_DBM: f64 = -68.0;
pub const NEAR_DBM: f64 = -64.0;
pub const DEFAULT_DEPARTURE_CONFIRM_SECONDS: f64 = 0.7;
pub const RECENT_MOTION_SECONDS: f64 = 5.0;
const MAX_EVALUATION_GAP_SECONDS: f64 = 0.75;

#[derive(Debug, Clone, Copy, PartialEq)]
struct RssiThresholds {
    hard_far_dbm: f64,
    far_dbm: f64,
    fast_far_dbm: f64,
    near_dbm: f64,
}

fn rssi_thresholds(departure_dbm: Option<f64>) -> RssiThresholds {
    match departure_dbm {
        Some(far_dbm) => RssiThresholds {
            hard_far_dbm: far_dbm - 8.0,
            far_dbm,
            fast_far_dbm: far_dbm + 4.0,
            near_dbm: far_dbm + 8.0,
        },
        None => RssiThresholds {
            hard_far_dbm: HARD_FAR_DBM,
            far_dbm: FAR_DBM,
            fast_far_dbm: FAST_FAR_DBM,
            near_dbm: NEAR_DBM,
        },
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ProtectionState {
    Disabled,
    Armed,
    Tripped,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TripReason {
    LinkLost,
    HardFar,
    MotionAndAway,
    SustainedFar,
}

impl TripReason {
    pub const fn code(self) -> &'static str {
        match self {
            Self::LinkLost => "L1",
            Self::HardFar => "L2",
            Self::MotionAndAway => "L3",
            Self::SustainedFar => "L4",
        }
    }

    pub const fn label(self) -> &'static str {
        match self {
            Self::LinkLost => "utrata świeżych pakietów z breloka",
            Self::HardFar => "bardzo słaby sygnał",
            Self::MotionAndAway => "ruch breloka i potwierdzony trend oddalania",
            Self::SustainedFar => "utrzymujący się słaby sygnał",
        }
    }
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LockAttemptStatus {
    #[default]
    None,
    Pending,
    Submitted,
    Failed,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProtectionSnapshot {
    pub state: ProtectionState,
    pub trip_reason: Option<TripReason>,
    pub lock_attempt: LockAttemptStatus,
    pub lock_error: Option<String>,
    pub far_evidence_s: f64,
}

#[derive(Debug, Default)]
pub struct ProtectionEngine {
    state: Option<ProtectionState>,
    trip_reason: Option<TripReason>,
    lock_attempt: LockAttemptStatus,
    lock_error: Option<String>,
    armed_at: Option<Duration>,
    last_tick_at: Option<Duration>,
    hard_far_since: Option<Duration>,
    fast_since: Option<Duration>,
    far_evidence_s: f64,
    near_since: Option<Duration>,
}

impl ProtectionEngine {
    pub fn state(&self) -> ProtectionState {
        self.state.unwrap_or(ProtectionState::Disabled)
    }

    /// Arm only with a selected, live device and warmed RSSI filter.
    pub fn arm(
        &mut self,
        now: Duration,
        device: Option<&DeviceSnapshot>,
    ) -> Result<(), &'static str> {
        let Some(device) = device else {
            return Err("Najpierw wybierz brelok w ustawieniach.");
        };
        if device.state != ConnectionState::Live || !device.telemetry_fresh {
            return Err("Brelok nie wysyła teraz świeżej telemetrii.");
        }
        if device.rssi_filtered_dbm.is_none() {
            return Err("Czekam na wystarczającą liczbę próbek RSSI.");
        }

        self.state = Some(ProtectionState::Armed);
        self.trip_reason = None;
        self.lock_attempt = LockAttemptStatus::None;
        self.lock_error = None;
        self.armed_at = Some(now);
        self.last_tick_at = Some(now);
        self.hard_far_since = None;
        self.fast_since = None;
        self.far_evidence_s = 0.0;
        self.near_since = None;
        Ok(())
    }

    pub fn disarm(&mut self) {
        self.state = Some(ProtectionState::Disabled);
        self.trip_reason = None;
        self.lock_attempt = LockAttemptStatus::None;
        self.lock_error = None;
        self.armed_at = None;
        self.last_tick_at = None;
        self.hard_far_since = None;
        self.fast_since = None;
        self.far_evidence_s = 0.0;
        self.near_since = None;
    }

    /// Evaluate once per backend tick. A returned reason is a one-shot lock request;
    /// the latched Tripped state prevents repeat requests until explicit rearming.
    pub fn update(
        &mut self,
        now: Duration,
        device: Option<&DeviceSnapshot>,
        lost_seconds: f64,
        departure_threshold_dbm: Option<f64>,
    ) -> Option<TripReason> {
        self.update_with_confirm_delay(
            now,
            device,
            lost_seconds,
            departure_threshold_dbm,
            DEFAULT_DEPARTURE_CONFIRM_SECONDS,
        )
    }

    /// As `update`, with a user-configurable confirmation time applied to every
    /// RSSI-based departure rule. Link loss continues to use `lost_seconds`.
    pub fn update_with_confirm_delay(
        &mut self,
        now: Duration,
        device: Option<&DeviceSnapshot>,
        lost_seconds: f64,
        departure_threshold_dbm: Option<f64>,
        departure_confirm_seconds: f64,
    ) -> Option<TripReason> {
        if self.state() == ProtectionState::Tripped {
            self.update_waiting_for_return(now, device, departure_threshold_dbm);
            return None;
        }
        if self.state() != ProtectionState::Armed {
            return None;
        }

        let evaluation_gap = self
            .last_tick_at
            .map(|previous| now.saturating_sub(previous).as_secs_f64())
            .unwrap_or(0.0);
        self.last_tick_at = Some(now);
        if evaluation_gap > MAX_EVALUATION_GAP_SECONDS {
            // A suspended or stalled evaluator cannot claim unobserved continuous
            // RSSI evidence. Link-loss timing still uses the packet age below.
            self.hard_far_since = None;
            self.fast_since = None;
            self.far_evidence_s = 0.0;
            self.near_since = None;
        }
        let elapsed = evaluation_gap.min(0.25);

        let age = device.and_then(|device| device.packet_age_s);
        if age.is_some_and(|age| age >= lost_seconds) {
            return self.trip(TripReason::LinkLost);
        }

        let thresholds = rssi_thresholds(departure_threshold_dbm);

        let fresh_rssi = device
            .filter(|device| device.state == ConnectionState::Live && device.telemetry_fresh)
            .and_then(|device| device.rssi_filtered_dbm);

        if let Some(rssi) = fresh_rssi {
            if rssi <= thresholds.hard_far_dbm {
                self.hard_far_since.get_or_insert(now);
            } else {
                self.hard_far_since = None;
            }

            let recent_motion = device.is_some_and(|device| {
                device.imu_valid
                    && !device.motion_age_saturated
                    && device
                        .motion_age_s
                        .is_some_and(|age| age <= RECENT_MOTION_SECONDS)
            });
            let confirmed_away = device.is_some_and(|device| {
                device.trend.quality == TrendQuality::Valid
                    && device
                        .trend
                        .slope_db_s
                        .is_some_and(|slope| slope <= -1.0 && slope * device.trend.span_s <= -4.0)
            });
            if rssi <= thresholds.fast_far_dbm && recent_motion && confirmed_away {
                self.fast_since.get_or_insert(now);
            } else {
                self.fast_since = None;
            }

            if rssi <= thresholds.far_dbm {
                self.far_evidence_s += elapsed;
                self.near_since = None;
            } else if rssi >= thresholds.near_dbm {
                let near_since = *self.near_since.get_or_insert(now);
                if now.saturating_sub(near_since).as_secs_f64() >= 1.0 {
                    self.far_evidence_s = 0.0;
                }
            } else {
                self.far_evidence_s = (self.far_evidence_s - elapsed * 0.5).max(0.0);
                self.near_since = None;
            }
        } else {
            // Stale samples cannot extend a continuous confirmation or add L4 evidence.
            self.hard_far_since = None;
            self.fast_since = None;
            self.near_since = None;
        }

        // Priority is stable when multiple rules become true in the same tick.
        let hard_far = self.hard_far_since.is_some_and(|since| {
            now.saturating_sub(since).as_secs_f64() >= departure_confirm_seconds
        });
        let fast = self.fast_since.is_some_and(|since| {
            now.saturating_sub(since).as_secs_f64() >= departure_confirm_seconds
        });
        if hard_far {
            return self.trip(TripReason::HardFar);
        }
        if fast {
            return self.trip(TripReason::MotionAndAway);
        }
        if self.far_evidence_s >= departure_confirm_seconds {
            return self.trip(TripReason::SustainedFar);
        }
        None
    }

    fn trip(&mut self, reason: TripReason) -> Option<TripReason> {
        self.state = Some(ProtectionState::Tripped);
        self.trip_reason = Some(reason);
        self.lock_attempt = LockAttemptStatus::Pending;
        self.lock_error = None;
        self.near_since = None;
        Some(reason)
    }

    fn update_waiting_for_return(
        &mut self,
        now: Duration,
        device: Option<&DeviceSnapshot>,
        departure_threshold_dbm: Option<f64>,
    ) {
        let near_dbm = rssi_thresholds(departure_threshold_dbm).near_dbm;
        let near = device
            .filter(|device| device.state == ConnectionState::Live && device.telemetry_fresh)
            .and_then(|device| device.rssi_filtered_dbm)
            .is_some_and(|rssi| rssi >= near_dbm);
        if !near {
            self.near_since = None;
            return;
        }

        let since = *self.near_since.get_or_insert(now);
        if now.saturating_sub(since).as_secs_f64() < 1.0 {
            return;
        }

        // Keep monitoring while the user is away. Clear the one-shot lock
        // result only after the selected fob is back near the computer for a
        // full second, so the next departure can trigger another lock.
        self.state = Some(ProtectionState::Armed);
        self.trip_reason = None;
        self.lock_attempt = LockAttemptStatus::None;
        self.lock_error = None;
        self.armed_at = Some(now);
        self.last_tick_at = Some(now);
        self.hard_far_since = None;
        self.fast_since = None;
        self.far_evidence_s = 0.0;
        self.near_since = None;
    }

    pub fn record_lock_attempt(&mut self, result: Result<(), String>) {
        if self.state() != ProtectionState::Tripped
            || self.lock_attempt != LockAttemptStatus::Pending
        {
            return;
        }
        match result {
            Ok(()) => {
                self.lock_attempt = LockAttemptStatus::Submitted;
                self.lock_error = None;
            }
            Err(error) => {
                self.lock_attempt = LockAttemptStatus::Failed;
                self.lock_error = Some(error);
            }
        }
    }

    pub fn snapshot(&self) -> ProtectionSnapshot {
        ProtectionSnapshot {
            state: self.state(),
            trip_reason: self.trip_reason,
            lock_attempt: self.lock_attempt,
            lock_error: self.lock_error.clone(),
            far_evidence_s: self.far_evidence_s,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn live_device(rssi: f64) -> DeviceSnapshot {
        DeviceSnapshot {
            device_id: crate::DeviceId::from_bytes([1, 2, 3, 4, 5, 6]),
            address: "test".into(),
            name: Some("breLock".into()),
            state: ConnectionState::Live,
            telemetry_fresh: true,
            packet_age_s: Some(0.1),
            callback_age_s: Some(0.1),
            rssi_raw_dbm: Some(rssi),
            rssi_filtered_dbm: Some(rssi),
            distance_estimate_m: Some(0.5),
            radial_speed_estimate_m_s: None,
            actual_speed_m_s: None,
            trend: crate::signal::TrendSnapshot {
                quality: TrendQuality::WarmingUp,
                points: 0,
                span_s: 0.0,
                coverage: 0.0,
                slope_db_s: None,
                r_squared: None,
            },
            motion: crate::monitor::MotionState::Still,
            motion_age_s: Some(0.0),
            motion_age_saturated: false,
            imu_valid: true,
            gyro_valid: true,
            acceleration_rms_mg: Some(5),
            gyro_rms_dps: Some(1.0),
            battery_mv: Some(4000),
            packet_hz: Some(5.0),
            counters: crate::monitor::PacketCounters::default(),
            last_packet: None,
        }
    }

    #[test]
    fn calibrated_threshold_moves_far_guards_and_near_hysteresis_together() {
        assert_eq!(
            rssi_thresholds(Some(-69.0)),
            RssiThresholds {
                hard_far_dbm: -77.0,
                far_dbm: -69.0,
                fast_far_dbm: -65.0,
                near_dbm: -61.0,
            }
        );
    }

    #[test]
    fn no_calibration_preserves_start_thresholds() {
        assert_eq!(
            rssi_thresholds(None),
            RssiThresholds {
                hard_far_dbm: HARD_FAR_DBM,
                far_dbm: FAR_DBM,
                fast_far_dbm: FAST_FAR_DBM,
                near_dbm: NEAR_DBM,
            }
        );
    }

    #[test]
    fn tripped_protection_stays_active_and_rearms_after_a_stable_return() {
        let mut engine = ProtectionEngine {
            state: Some(ProtectionState::Tripped),
            trip_reason: Some(TripReason::HardFar),
            lock_attempt: LockAttemptStatus::Submitted,
            ..ProtectionEngine::default()
        };
        let near = live_device(-60.0);

        engine.update(Duration::ZERO, Some(&near), 6.0, None);
        assert_eq!(engine.state(), ProtectionState::Tripped);
        assert_eq!(engine.snapshot().lock_attempt, LockAttemptStatus::Submitted);

        engine.update(Duration::from_millis(999), Some(&near), 6.0, None);
        assert_eq!(engine.state(), ProtectionState::Tripped);
        engine.update(Duration::from_secs(1), Some(&near), 6.0, None);

        assert_eq!(engine.state(), ProtectionState::Armed);
        assert_eq!(engine.snapshot().trip_reason, None);
        assert_eq!(engine.snapshot().lock_attempt, LockAttemptStatus::None);
        assert_eq!(
            engine.update(Duration::from_millis(1200), Some(&near), 6.0, None),
            None
        );
    }

    #[test]
    fn tripped_protection_does_not_rearm_while_the_fob_is_away_or_stale() {
        let mut engine = ProtectionEngine {
            state: Some(ProtectionState::Tripped),
            trip_reason: Some(TripReason::HardFar),
            lock_attempt: LockAttemptStatus::Submitted,
            ..ProtectionEngine::default()
        };
        let far = live_device(-75.0);
        for second in 0..5 {
            engine.update(Duration::from_secs(second), Some(&far), 6.0, None);
        }
        assert_eq!(engine.state(), ProtectionState::Tripped);

        let mut stale = live_device(-60.0);
        stale.telemetry_fresh = false;
        stale.state = ConnectionState::Stale;
        for second in 5..10 {
            engine.update(Duration::from_secs(second), Some(&stale), 6.0, None);
        }
        assert_eq!(engine.state(), ProtectionState::Tripped);
    }
}
