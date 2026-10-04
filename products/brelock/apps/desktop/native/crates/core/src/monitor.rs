use crate::{
    AppConfig, DeviceId, TelemetryPacket,
    config::ConfigError,
    signal::{SignalFilter, TrendSnapshot, estimate_distance, estimate_radial_speed},
};
use serde::Serialize;
use std::{collections::VecDeque, time::Duration};

/// Keep the last RSSI estimate through short host-side BLE callback gaps.
/// Telemetry freshness remains controlled by `AppConfig::fresh_seconds`.
pub const RSSI_HOLD_SECONDS: f64 = 3.0;

#[derive(Debug, Clone)]
pub struct Observation {
    pub received_at: Duration,
    pub address: String,
    pub name: Option<String>,
    pub rssi_dbm: Option<i16>,
    pub telemetry: TelemetryPacket,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReceiveDisposition {
    New,
    Duplicate,
    Reboot,
    OutOfOrder,
    OldBoot,
    Conflict,
    Foreign,
    OldTimestamp,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ConnectionState {
    Waiting,
    Live,
    Stale,
    Lost,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotionState {
    Unknown,
    Still,
    Moving,
}

#[derive(Debug, Default, Clone, Serialize)]
pub struct PacketCounters {
    pub callbacks: u64,
    pub new_packets: u64,
    pub duplicates: u64,
    pub out_of_order: u64,
    pub conflicting_duplicates: u64,
    pub skipped_summaries: u64,
    pub reboots: u64,
    pub signal_resets: u64,
    pub invalid_rssi: u64,
    pub old_timestamps: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct DeviceSnapshot {
    pub device_id: DeviceId,
    pub address: String,
    pub name: Option<String>,
    pub state: ConnectionState,
    pub telemetry_fresh: bool,
    pub packet_age_s: Option<f64>,
    pub callback_age_s: Option<f64>,
    pub rssi_raw_dbm: Option<f64>,
    pub rssi_filtered_dbm: Option<f64>,
    pub distance_estimate_m: Option<f64>,
    pub radial_speed_estimate_m_s: Option<f64>,
    pub actual_speed_m_s: Option<f64>,
    pub trend: TrendSnapshot,
    pub motion: MotionState,
    pub motion_age_s: Option<f64>,
    pub motion_age_saturated: bool,
    pub imu_valid: bool,
    pub gyro_valid: bool,
    pub acceleration_rms_mg: Option<u16>,
    pub gyro_rms_dps: Option<f64>,
    pub battery_mv: Option<u16>,
    pub packet_hz: Option<f64>,
    pub counters: PacketCounters,
    /// Last received values for inspection; NEVER interpret as current if stale.
    pub last_packet: Option<TelemetryPacket>,
}

pub struct DeviceMonitor {
    device_id: DeviceId,
    config: AppConfig,
    address: String,
    name: Option<String>,
    packet: Option<TelemetryPacket>,
    last_packet_at: Option<Duration>,
    last_callback_at: Option<Duration>,
    rssi: Option<(Duration, f64)>,
    signal: SignalFilter,
    retired_boots: VecDeque<u16>,
    new_times: VecDeque<f64>,
    started_at: Option<f64>,
    counts: PacketCounters,
}

impl DeviceMonitor {
    pub fn new(device_id: DeviceId, config: AppConfig) -> Result<Self, ConfigError> {
        config.validate()?;
        Ok(Self {
            device_id,
            config,
            address: String::new(),
            name: None,
            packet: None,
            last_packet_at: None,
            last_callback_at: None,
            rssi: None,
            signal: SignalFilter::default(),
            retired_boots: VecDeque::new(),
            new_times: VecDeque::new(),
            started_at: None,
            counts: PacketCounters::default(),
        })
    }

    pub fn receive(&mut self, observation: Observation) -> ReceiveDisposition {
        let packet = &observation.telemetry;
        if packet.device_id != self.device_id {
            return ReceiveDisposition::Foreign;
        }
        let at = observation.received_at;
        if self.last_callback_at.is_some_and(|previous| at < previous) {
            self.counts.old_timestamps += 1;
            return ReceiveDisposition::OldTimestamp;
        }
        self.last_callback_at = Some(at);
        self.counts.callbacks += 1;
        self.address = observation.address;
        if observation.name.is_some() {
            self.name = observation.name;
        }
        let mut disposition = ReceiveDisposition::New;
        if let Some(previous) = &self.packet {
            if packet.boot_id != previous.boot_id {
                if self.retired_boots.contains(&packet.boot_id) {
                    self.counts.out_of_order += 1;
                    return ReceiveDisposition::OldBoot;
                }
                if self.retired_boots.len() == 16 {
                    self.retired_boots.pop_front();
                }
                self.retired_boots.push_back(previous.boot_id);
                self.counts.reboots += 1;
                disposition = ReceiveDisposition::Reboot;
            } else {
                let delta = packet.sequence.wrapping_sub(previous.sequence);
                if delta == 0 {
                    if packet != previous {
                        self.counts.conflicting_duplicates += 1;
                        return ReceiveDisposition::Conflict;
                    }
                    self.counts.duplicates += 1;
                    if self.last_packet_at.is_some_and(|previous_at| {
                        at.saturating_sub(previous_at).as_secs_f64()
                            <= self.signal_retention_seconds()
                    }) {
                        self.add_rssi(at, observation.rssi_dbm);
                    }
                    return ReceiveDisposition::Duplicate;
                }
                if delta >= 0x8000_0000 {
                    self.counts.out_of_order += 1;
                    return ReceiveDisposition::OutOfOrder;
                }
                self.counts.skipped_summaries += u64::from(delta - 1);
            }
        }
        if disposition == ReceiveDisposition::Reboot
            || self.last_packet_at.is_some_and(|previous_at| {
                at.saturating_sub(previous_at).as_secs_f64() > self.signal_retention_seconds()
            })
        {
            self.reset_signal();
        }
        self.packet = Some(observation.telemetry);
        self.last_packet_at = Some(at);
        self.counts.new_packets += 1;
        let seconds = at.as_secs_f64();
        self.started_at.get_or_insert(seconds);
        self.new_times.push_back(seconds);
        self.prune_rates(seconds);
        self.add_rssi(at, observation.rssi_dbm);
        disposition
    }

    fn reset_signal(&mut self) {
        self.signal = SignalFilter::default();
        self.rssi = None;
        self.counts.signal_resets += 1;
    }

    fn signal_retention_seconds(&self) -> f64 {
        self.config.fresh_seconds.max(RSSI_HOLD_SECONDS)
    }

    fn add_rssi(&mut self, at: Duration, rssi: Option<i16>) {
        let Some(rssi) = rssi.filter(|rssi| (-127..=20).contains(rssi)) else {
            self.counts.invalid_rssi += 1;
            return;
        };
        if self.rssi.is_some_and(|(previous, _)| {
            at.saturating_sub(previous).as_secs_f64() > self.signal_retention_seconds()
        }) {
            self.reset_signal();
        }
        self.rssi = Some((at, f64::from(rssi)));
        self.signal.add(at.as_secs_f64(), f64::from(rssi));
    }

    fn prune_rates(&mut self, at: f64) {
        while self.new_times.front().is_some_and(|time| *time < at - 5.0) {
            self.new_times.pop_front();
        }
    }

    pub fn snapshot(&mut self, at: Duration) -> DeviceSnapshot {
        let seconds = at.as_secs_f64();
        self.signal.advance(seconds);
        self.prune_rates(seconds);
        let age = self
            .last_packet_at
            .map(|previous| at.saturating_sub(previous).as_secs_f64());
        let fresh = age.is_some_and(|age| age <= self.config.fresh_seconds);
        let state = match age {
            None => ConnectionState::Waiting,
            Some(age) if age >= self.config.lost_seconds => ConnectionState::Lost,
            Some(_) if !fresh => ConnectionState::Stale,
            _ => ConnectionState::Live,
        };
        let rssi = self
            .rssi
            .filter(|(previous, _)| {
                at.saturating_sub(*previous).as_secs_f64() <= self.signal_retention_seconds()
            })
            .map(|(_, rssi)| rssi);
        let filtered = rssi.and(self.signal.filtered());
        let trend = self.signal.trend(fresh && rssi.is_some());
        let distance = filtered.and_then(|rssi| estimate_distance(rssi, &self.config));
        let speed =
            distance.and_then(|distance| estimate_radial_speed(distance, &trend, &self.config));
        let current = self.packet.as_ref().filter(|_| fresh);
        let imu = current.filter(|packet| packet.imu_valid);
        let rate = self.started_at.and_then(|start| {
            let duration = seconds - start;
            (duration >= 1.0).then(|| self.new_times.len() as f64 / duration.min(5.0))
        });
        DeviceSnapshot {
            device_id: self.device_id,
            address: self.address.clone(),
            name: self.name.clone(),
            state,
            telemetry_fresh: fresh,
            packet_age_s: age,
            callback_age_s: self
                .last_callback_at
                .map(|previous| at.saturating_sub(previous).as_secs_f64()),
            rssi_raw_dbm: rssi,
            rssi_filtered_dbm: filtered,
            distance_estimate_m: distance,
            radial_speed_estimate_m_s: speed,
            actual_speed_m_s: None,
            trend,
            motion: match imu.and_then(|packet| packet.moving) {
                Some(true) => MotionState::Moving,
                Some(false) => MotionState::Still,
                None => MotionState::Unknown,
            },
            motion_age_s: imu
                .and_then(|packet| packet.motion_age_ms)
                .map(|motion_age| f64::from(motion_age) / 1000.0 + age.unwrap_or(0.0)),
            motion_age_saturated: imu.is_some_and(|packet| packet.motion_age_saturated),
            imu_valid: imu.is_some(),
            gyro_valid: imu.is_some_and(|packet| packet.gyro_valid),
            acceleration_rms_mg: imu.and_then(|packet| packet.acceleration_rms_mg),
            gyro_rms_dps: imu.and_then(|packet| packet.gyro_rms_dps),
            battery_mv: current.and_then(|packet| packet.battery_mv),
            packet_hz: rate,
            counters: self.counts.clone(),
            last_packet: self.packet.clone(),
        }
    }
}
