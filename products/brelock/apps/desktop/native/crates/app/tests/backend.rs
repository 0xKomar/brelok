use brelock_core::{AppConfig, DeviceId, monitor::ConnectionState, protocol::decode_hex};
use brelock_desktop::backend::{Backend, BackendEvent};
use brelock_desktop::calibration::CalibrationResult;
use brelock_platform::ble::RawAdvertisement;
use std::time::Duration;

fn raw() -> RawAdvertisement {
    RawAdvertisement {
        received_at: Duration::ZERO,
        address: "OS-UUID".into(),
        name: None,
        rssi_dbm: Some(-59),
        payload: decode_hex("0201123456789ABC3412EFCDAB89177B00C8011503A00FFD").unwrap(),
    }
}

#[test]
fn application_api_selects_by_hardware_id_without_gui_or_advertised_name() {
    let mut backend = Backend::new(AppConfig::default()).unwrap();
    backend.receive(raw()).unwrap();
    let id: DeviceId = "123456789ABC".parse().unwrap();
    backend.select_device(id).unwrap();
    let snapshot = backend.snapshot(Duration::from_millis(100));
    assert_eq!(snapshot.selected.unwrap().device_id, id);
    assert_eq!(snapshot.devices.len(), 1);
    assert!(!snapshot.capabilities.session_lock);
}

#[test]
fn malformed_data_and_another_device_do_not_refresh_the_selected_keyfob() {
    let id: DeviceId = "AABBCCDDEEFF".parse().unwrap();
    let mut backend = Backend::new(AppConfig {
        device_id: Some(id),
        ..AppConfig::default()
    })
    .unwrap();
    backend.receive(raw()).unwrap();
    let mut malformed = raw();
    malformed.payload.pop();
    assert!(matches!(
        backend.receive(malformed).unwrap(),
        BackendEvent::InvalidPacket { .. }
    ));
    let snapshot = backend.snapshot(Duration::from_secs(10));
    assert_eq!(snapshot.selected.unwrap().state, ConnectionState::Waiting);
    assert_eq!(snapshot.invalid_packets, 1);
}

#[test]
fn invalid_configuration_does_not_destroy_active_state() {
    let id: DeviceId = "123456789ABC".parse().unwrap();
    let mut backend = Backend::new(AppConfig {
        device_id: Some(id),
        ..AppConfig::default()
    })
    .unwrap();
    backend.receive(raw()).unwrap();
    assert!(
        backend
            .configure(AppConfig {
                lost_seconds: 0.1,
                ..AppConfig::default()
            })
            .is_err()
    );
    assert_eq!(
        backend
            .snapshot(Duration::from_millis(100))
            .selected
            .unwrap()
            .state,
        ConnectionState::Live
    );
}

#[test]
fn learned_departure_threshold_is_exposed_in_local_configuration() {
    let mut backend = Backend::new(AppConfig::default()).unwrap();
    backend.set_departure_threshold_dbm(-69.0).unwrap();
    assert_eq!(
        backend
            .snapshot(Duration::from_secs(1))
            .config
            .departure_threshold_dbm,
        Some(-69.0)
    );
}

#[test]
fn fitted_distance_reaches_the_selected_device_snapshot() {
    let id: DeviceId = "123456789ABC".parse().unwrap();
    let mut backend = Backend::new(AppConfig {
        device_id: Some(id),
        ..AppConfig::default()
    })
    .unwrap();
    for sequence in 0u32..3 {
        let mut packet = raw();
        packet.received_at = Duration::from_millis(sequence as u64 * 250);
        packet.payload[10..14].copy_from_slice(&sequence.to_le_bytes());
        backend.receive(packet).unwrap();
    }
    let before = backend.snapshot(Duration::from_millis(750));
    assert_eq!(before.selected.unwrap().distance_estimate_m, Some(1.0));
    let result = CalibrationResult {
        median_dbm: -59.0,
        threshold_dbm: -62.0,
        mad_db: 0.0,
        margin_db: 3.0,
        sample_count: 12,
    };
    backend
        .configure(result.calibrated_config(&before.config, 4.0).unwrap())
        .unwrap();
    for sequence in 4u32..7 {
        let mut packet = raw();
        packet.received_at = Duration::from_millis(sequence as u64 * 250);
        packet.payload[10..14].copy_from_slice(&sequence.to_le_bytes());
        backend.receive(packet).unwrap();
    }
    let after = backend.snapshot(Duration::from_millis(1750));
    assert!((after.selected.unwrap().distance_estimate_m.unwrap() - 4.0).abs() < 1e-9);
    assert_eq!(after.config.departure_threshold_dbm, Some(-62.0));
}
