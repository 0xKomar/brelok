use anyhow::Result;
use brelock_core::{
    AppConfig, DeviceId, DeviceMonitor, DeviceSnapshot, Observation, ProtectionEngine,
    ProtectionSnapshot, ProtectionState, ReceiveDisposition, TelemetryPacket, TripReason,
    decode_telemetry, protocol::payload_hex,
};
use brelock_platform::{
    ble::{RawAdvertisement, TransportEvent, TransportState},
    system::{PlatformCapabilities, capabilities},
};
use serde::Serialize;
use std::{collections::BTreeMap, time::Duration};

#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ApplicationMode {
    Observe,
    Armed,
    Tripped,
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum BackendEvent {
    Packet {
        t_s: f64,
        payload_hex: String,
        disposition: ReceiveDisposition,
        telemetry: TelemetryPacket,
    },
    InvalidPacket {
        t_s: f64,
        payload_hex: String,
        error: String,
    },
    IgnoredPacket {
        t_s: f64,
        reason: &'static str,
    },
}

#[derive(Debug, Clone, Serialize)]
pub struct AppSnapshot {
    pub t_s: f64,
    pub mode: ApplicationMode,
    pub transport: TransportState,
    pub config: AppConfig,
    pub selected: Option<DeviceSnapshot>,
    pub devices: Vec<DeviceSnapshot>,
    pub capabilities: PlatformCapabilities,
    pub protection: ProtectionSnapshot,
    pub invalid_packets: u64,
    pub transport_errors: u64,
    pub last_error: Option<String>,
}

/// The public application boundary for a future desktop shell. A shell selects
/// an ID, configures the backend, supplies transport events and reads snapshots.
/// UI frameworks and OS side effects never participate in measurement logic.
pub struct Backend {
    config: AppConfig,
    devices: BTreeMap<String, DeviceMonitor>,
    transport: TransportState,
    invalid_packets: u64,
    transport_errors: u64,
    last_error: Option<String>,
    protection: ProtectionEngine,
}

impl Backend {
    pub fn new(config: AppConfig) -> Result<Self> {
        config.validate()?;
        let mut backend = Self {
            config,
            devices: BTreeMap::new(),
            transport: TransportState::Starting,
            invalid_packets: 0,
            transport_errors: 0,
            last_error: None,
            protection: ProtectionEngine::default(),
        };
        if let Some(id) = backend.config.device_id {
            backend.select_device(id)?;
        }
        Ok(backend)
    }

    pub fn select_device(&mut self, id: DeviceId) -> Result<()> {
        if self.config.device_id != Some(id) {
            self.protection.disarm();
        }
        let key = id.to_string();
        if !self.devices.contains_key(&key) {
            self.devices
                .insert(key, DeviceMonitor::new(id, self.config.clone())?);
        }
        self.config.device_id = Some(id);
        Ok(())
    }

    /// Validate first; changing parameters clears affected measurement history.
    pub fn configure(&mut self, config: AppConfig) -> Result<()> {
        let replacement = Self::new(config)?;
        self.protection.disarm();
        self.config = replacement.config;
        self.devices = replacement.devices;
        // Configuration changes do not restart the BLE scanner. Keep its live
        // state and counters so protection can be armed after selecting a key fob.
        Ok(())
    }

    pub fn transport_event(&mut self, event: TransportEvent) -> Result<Option<BackendEvent>> {
        match event {
            TransportEvent::Status { state, detail } => {
                self.transport = state;
                if state == TransportState::Unavailable {
                    self.transport_errors += 1;
                    self.last_error = detail;
                }
                Ok(None)
            }
            TransportEvent::Advertisement { advertisement } => {
                self.receive(advertisement).map(Some)
            }
            TransportEvent::ControlLink { .. } | TransportEvent::Control { .. } => Ok(None),
        }
    }

    pub fn receive(&mut self, raw: RawAdvertisement) -> Result<BackendEvent> {
        let t_s = raw.received_at.as_secs_f64();
        let packet = match decode_telemetry(&raw.payload) {
            Ok(packet) => packet,
            Err(error) => {
                self.invalid_packets += 1;
                self.last_error = Some(error.to_string());
                return Ok(BackendEvent::InvalidPacket {
                    t_s,
                    payload_hex: payload_hex(&raw.payload),
                    error: error.to_string(),
                });
            }
        };
        let key = packet.device_id.to_string();
        if !self.devices.contains_key(&key) {
            if self.devices.len() >= 64 {
                return Ok(BackendEvent::IgnoredPacket {
                    t_s,
                    reason: "discovery limit reached",
                });
            }
            self.devices.insert(
                key.clone(),
                DeviceMonitor::new(packet.device_id, self.config.clone())?,
            );
        }
        let monitor = self
            .devices
            .get_mut(&key)
            .expect("monitor was inserted above");
        let disposition = monitor.receive(Observation {
            received_at: raw.received_at,
            address: raw.address,
            name: raw.name,
            rssi_dbm: raw.rssi_dbm,
            telemetry: packet.clone(),
        });
        Ok(BackendEvent::Packet {
            t_s,
            payload_hex: payload_hex(&raw.payload),
            disposition,
            telemetry: packet,
        })
    }

    pub fn snapshot(&mut self, at: Duration) -> AppSnapshot {
        let devices: Vec<_> = self
            .devices
            .values_mut()
            .map(|monitor| monitor.snapshot(at))
            .collect();
        let selected = self.config.device_id.and_then(|id| {
            devices
                .iter()
                .find(|device| device.device_id == id)
                .cloned()
        });
        let protection = self.protection.snapshot();
        AppSnapshot {
            t_s: at.as_secs_f64(),
            mode: match protection.state {
                ProtectionState::Disabled => ApplicationMode::Observe,
                ProtectionState::Armed => ApplicationMode::Armed,
                ProtectionState::Tripped => ApplicationMode::Tripped,
            },
            transport: self.transport,
            config: self.config.clone(),
            selected,
            devices,
            capabilities: capabilities(),
            protection,
            invalid_packets: self.invalid_packets,
            transport_errors: self.transport_errors,
            last_error: self.last_error.clone(),
        }
    }

    pub fn arm_protection(&mut self, at: Duration) -> std::result::Result<(), &'static str> {
        if self.transport != TransportState::Scanning {
            return Err(
                "Skanowanie Bluetooth nie jest aktywne. Poczekaj na połączenie z brelokiem.",
            );
        }
        let selected = self.snapshot(at).selected;
        if self.protection.state() == ProtectionState::Tripped {
            let near_dbm = self
                .config
                .departure_threshold_dbm
                .map_or(brelock_core::protection::NEAR_DBM, |threshold| {
                    threshold + 8.0
                });
            if selected
                .as_ref()
                .and_then(|device| device.rssi_filtered_dbm)
                .is_none_or(|rssi| rssi < near_dbm)
            {
                return Err("Wróć bliżej komputera z brelokiem, aby ponownie uzbroić ochronę.");
            }
        }
        self.protection.arm(at, selected.as_ref())
    }

    pub fn disarm_protection(&mut self) {
        self.protection.disarm();
    }

    pub fn set_departure_threshold_dbm(&mut self, threshold: f64) -> Result<()> {
        let mut config = self.config.clone();
        config.departure_threshold_dbm = Some(threshold);
        config.validate()?;
        self.config = config;
        self.protection.disarm();
        Ok(())
    }

    /// Snapshot, evaluate rules and return a one-shot request for the platform adapter.
    pub fn tick(&mut self, at: Duration) -> (AppSnapshot, Option<TripReason>, bool) {
        let mut snapshot = self.snapshot(at);
        let was_tripped = snapshot.protection.state == ProtectionState::Tripped;
        let reason = self.protection.update_with_confirm_delay(
            at,
            snapshot.selected.as_ref(),
            self.config.lost_seconds,
            self.config.departure_threshold_dbm,
            self.config.departure_confirm_seconds,
        );
        snapshot.protection = self.protection.snapshot();
        snapshot.mode = match snapshot.protection.state {
            ProtectionState::Disabled => ApplicationMode::Observe,
            ProtectionState::Armed => ApplicationMode::Armed,
            ProtectionState::Tripped => ApplicationMode::Tripped,
        };
        let auto_rearmed = was_tripped && snapshot.protection.state == ProtectionState::Armed;
        (snapshot, reason, auto_rearmed)
    }

    pub fn record_lock_attempt(&mut self, result: std::result::Result<(), String>) {
        self.protection.record_lock_attempt(result);
    }
}
