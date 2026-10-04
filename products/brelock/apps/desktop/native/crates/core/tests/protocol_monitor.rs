use brelock_core::{
    AppConfig, DeviceId, DeviceMonitor, Observation, ReceiveDisposition, TelemetryPacket,
    decode_telemetry,
    monitor::{ConnectionState, MotionState},
    protocol::{ProtocolError, decode_hex},
    signal::TrendQuality,
};
use std::time::Duration;

// Same literal bytes as firmware-esp32/tests/firmware_tests.cpp:testPacket.
const GOLDEN: &str = "0201123456789ABC3412EFCDAB89177B00C8011503A00FFD";

fn packet(sequence: u32) -> TelemetryPacket {
    let mut packet = decode_telemetry(&decode_hex(GOLDEN).unwrap()).unwrap();
    packet.sequence = sequence;
    packet
}

#[test]
fn v3_touch_marker_is_decoded_and_v2_keeps_its_legacy_tx_byte() {
    let mut raw = decode_hex(GOLDEN).unwrap();
    raw[0] = 3;
    raw[14] |= 1 << 5;
    raw[23] = 42;
    let packet = decode_telemetry(&raw).unwrap();
    assert_eq!(packet.protocol_version, 3);
    assert!(packet.button_event_active);
    assert_eq!(packet.button_event_count, Some(42));
    assert_eq!(packet.nominal_tx_dbm, 3);

    let legacy = decode_telemetry(&decode_hex(GOLDEN).unwrap()).unwrap();
    assert_eq!(legacy.protocol_version, 2);
    assert!(!legacy.button_event_active);
    assert_eq!(legacy.button_event_count, None);
    assert_eq!(legacy.nominal_tx_dbm, -3);
}

fn observation(sequence: u32, seconds: f64, rssi: i16) -> Observation {
    Observation {
        received_at: Duration::from_secs_f64(seconds),
        address: "OS-UUID".into(),
        name: None,
        rssi_dbm: Some(rssi),
        telemetry: packet(sequence),
    }
}

fn monitor() -> DeviceMonitor {
    DeviceMonitor::new("123456789ABC".parse().unwrap(), AppConfig::default()).unwrap()
}

#[test]
fn firmware_wire_format_has_correct_byte_order_and_units() {
    let packet = decode_telemetry(&decode_hex(GOLDEN).unwrap()).unwrap();
    assert_eq!(packet.device_id.to_string(), "123456789ABC");
    assert_eq!(packet.boot_id, 0x1234);
    assert_eq!(packet.sequence, 0x89abcdef);
    assert_eq!(packet.acceleration_rms_mg, Some(123));
    assert_eq!(packet.gyro_rms_dps, Some(45.6));
    assert_eq!(packet.motion_age_ms, Some(789));
    assert_eq!(packet.battery_mv, Some(4000));
    assert_eq!(packet.nominal_tx_dbm, -3);
}

#[test]
fn arbitrary_length_and_invalid_hex_never_read_out_of_bounds() {
    for size in 0..=40 {
        assert!(decode_telemetry(&vec![0; size]).is_err());
    }
    for hex in ["0", "XY", "💥", "A1💥"] {
        assert!(decode_hex(hex).is_err());
    }
}

#[test]
fn sensor_sentinels_and_clipping_cannot_be_mistaken_for_zero_motion() {
    let mut raw = decode_hex(GOLDEN).unwrap();
    raw[14] = 0x08;
    raw[15..19].fill(0);
    raw[19..21].fill(255);
    raw[21..23].fill(0);
    let packet = decode_telemetry(&raw).unwrap();
    assert!(packet.clipped);
    assert_eq!(packet.moving, None);
    assert_eq!(packet.acceleration_rms_mg, None);
    assert_eq!(packet.gyro_rms_dps, None);
    assert_eq!(packet.battery_mv, None);
    raw[14] = 0x0a;
    assert!(matches!(
        decode_telemetry(&raw),
        Err(ProtocolError::InvalidFlags)
    ));
}

#[test]
fn saturated_motion_age_differs_from_unknown_and_invalid_battery_is_rejected() {
    let mut raw = decode_hex(GOLDEN).unwrap();
    raw[19..21].copy_from_slice(&65534u16.to_le_bytes());
    assert!(decode_telemetry(&raw).unwrap().motion_age_saturated);
    raw[19..21].fill(255);
    assert_eq!(decode_telemetry(&raw).unwrap().motion_age_ms, None);
    raw[21..23].copy_from_slice(&2000u16.to_le_bytes());
    assert!(matches!(
        decode_telemetry(&raw),
        Err(ProtocolError::InvalidBattery)
    ));
}

#[test]
fn hardware_id_roundtrips_as_validated_hex_not_as_os_uuid() {
    let id: DeviceId = "00:01:02:AB:CD:EF".parse().unwrap();
    assert_eq!(serde_json::to_string(&id).unwrap(), "\"000102ABCDEF\"");
    assert!(serde_json::from_str::<DeviceId>("\"OS-UUID\"").is_err());
    assert_eq!(id, serde_json::from_str("\"000102abcdef\"").unwrap());
}

#[test]
fn defaults_are_valid_and_nonfinite_or_inconsistent_settings_fail() {
    AppConfig::default().validate().unwrap();
    let old_config = r#"{"schema_version":1,"device_id":null,"reference_rssi_dbm":-59,"path_loss_exponent":2.2,"fresh_seconds":1.5,"lost_seconds":6,"refresh_hz":5}"#;
    assert_eq!(
        serde_json::from_str::<AppConfig>(old_config)
            .unwrap()
            .calibration_distance_m,
        3.0
    );
    assert_eq!(
        serde_json::from_str::<AppConfig>(old_config)
            .unwrap()
            .departure_threshold_dbm,
        None
    );
    assert!(
        AppConfig {
            departure_threshold_dbm: Some(-69.0),
            ..AppConfig::default()
        }
        .validate()
        .is_ok()
    );
    assert!(
        AppConfig {
            departure_threshold_dbm: Some(f64::NAN),
            ..AppConfig::default()
        }
        .validate()
        .is_err()
    );
    for value in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        assert!(
            AppConfig {
                path_loss_exponent: value,
                ..AppConfig::default()
            }
            .validate()
            .is_err()
        );
    }
    for value in [0.0, 0.49, 20.1, f64::NAN, f64::INFINITY] {
        assert!(
            AppConfig {
                calibration_distance_m: value,
                ..AppConfig::default()
            }
            .validate()
            .is_err()
        );
    }
    assert!(
        AppConfig {
            lost_seconds: 1.0,
            ..AppConfig::default()
        }
        .validate()
        .is_err()
    );
    assert!(
        serde_json::from_str::<AppConfig>("{\"control_url\":\"https://example.org\"}").is_err()
    );
}

#[test]
fn never_seen_is_waiting_without_stationary_sensor_values() {
    let snapshot = monitor().snapshot(Duration::from_secs(30));
    assert_eq!(snapshot.state, ConnectionState::Waiting);
    assert_eq!(snapshot.motion, MotionState::Unknown);
    assert_eq!(snapshot.battery_mv, None);
}

#[test]
fn duplicates_never_refresh_heartbeat_or_imu() {
    let mut monitor = monitor();
    monitor.receive(observation(1, 0.0, -59));
    for index in 1..=70 {
        assert_eq!(
            monitor.receive(observation(1, f64::from(index) / 10.0, -60)),
            ReceiveDisposition::Duplicate
        );
    }
    let snapshot = monitor.snapshot(Duration::from_secs(7));
    assert_eq!(snapshot.state, ConnectionState::Lost);
    assert_eq!(snapshot.packet_age_s, Some(7.0));
    assert_eq!(snapshot.callback_age_s, Some(0.0));
    assert_eq!(snapshot.acceleration_rms_mg, None);
    assert_eq!(snapshot.distance_estimate_m, None);
    assert_eq!(snapshot.counters.new_packets, 1);
    assert_eq!(snapshot.counters.duplicates, 70);
}

#[test]
fn sparse_ble_callbacks_keep_a_filtered_rssi_without_refreshing_telemetry() {
    let mut monitor = monitor();
    monitor.receive(observation(1, 0.0, -52));
    monitor.receive(observation(2, 1.7, -53));
    monitor.receive(observation(3, 3.4, -51));

    let live = monitor.snapshot(Duration::from_secs_f64(3.4));
    assert_eq!(live.state, ConnectionState::Live);
    assert_eq!(live.rssi_raw_dbm, Some(-51.0));
    assert!(live.rssi_filtered_dbm.is_some());

    let stale = monitor.snapshot(Duration::from_secs_f64(5.0));
    assert_eq!(stale.state, ConnectionState::Stale);
    assert!(!stale.telemetry_fresh);
    // The signal remains useful for diagnostics/calibration briefly, but the
    // protection engine still requires fresh telemetry before using it.
    assert!(stale.rssi_filtered_dbm.is_some());
}

#[test]
fn wrap_old_packets_and_conflicting_duplicates_preserve_latest_state() {
    let mut monitor = monitor();
    monitor.receive(observation(u32::MAX, 0.0, -59));
    assert_eq!(
        monitor.receive(observation(1, 0.2, -59)),
        ReceiveDisposition::New
    );
    assert_eq!(
        monitor.receive(observation(0, 0.3, -100)),
        ReceiveDisposition::OutOfOrder
    );
    let mut changed = observation(1, 0.4, -100);
    changed.telemetry.battery_mv = Some(3900);
    assert_eq!(monitor.receive(changed), ReceiveDisposition::Conflict);
    let snapshot = monitor.snapshot(Duration::from_secs_f64(0.5));
    assert_eq!(snapshot.counters.skipped_summaries, 1);
    assert_eq!(snapshot.last_packet.unwrap().sequence, 1);
    assert_eq!(snapshot.battery_mv, Some(4000));
}

#[test]
fn old_boot_and_foreign_id_cannot_refresh_selected_keyfob() {
    let mut monitor = monitor();
    monitor.receive(observation(10, 0.0, -59));
    let mut reboot = observation(0, 0.2, -59);
    reboot.telemetry.boot_id = 5678;
    assert_eq!(monitor.receive(reboot), ReceiveDisposition::Reboot);
    assert_eq!(
        monitor.receive(observation(11, 0.3, -100)),
        ReceiveDisposition::OldBoot
    );
    let mut foreign = observation(12, 0.4, -100);
    foreign.telemetry.device_id = "AABBCCDDEEFF".parse().unwrap();
    assert_eq!(monitor.receive(foreign), ReceiveDisposition::Foreign);
    let snapshot = monitor.snapshot(Duration::from_secs_f64(0.5));
    assert_eq!(snapshot.last_packet.unwrap().boot_id, 5678);
    assert_eq!(snapshot.counters.reboots, 1);
}

#[test]
fn a_monotonic_clock_regression_is_ignored() {
    let mut monitor = monitor();
    monitor.receive(observation(10, 1.0, -59));
    assert_eq!(
        monitor.receive(observation(11, 0.5, -100)),
        ReceiveDisposition::OldTimestamp
    );
    assert_eq!(
        monitor
            .snapshot(Duration::from_secs(2))
            .last_packet
            .unwrap()
            .sequence,
        10
    );
}

#[test]
fn distance_filters_need_real_buckets_and_radial_speed_has_correct_sign() {
    for direction in [-1.0, 1.0] {
        let mut monitor = monitor();
        for index in 0..40 {
            let at = f64::from(index) * 0.2;
            monitor.receive(observation(
                index,
                at,
                (-70.0 + direction * 3.0 * at).round() as i16,
            ));
        }
        let snapshot = monitor.snapshot(Duration::from_secs_f64(7.9));
        assert_eq!(snapshot.trend.quality, TrendQuality::Valid);
        assert!(snapshot.trend.r_squared.unwrap() > 0.98);
        assert_eq!(
            snapshot.radial_speed_estimate_m_s.unwrap().signum(),
            -direction
        );
        assert_eq!(snapshot.actual_speed_m_s, None);
    }
    let mut monitor = monitor();
    monitor.receive(observation(1, 0.0, -59));
    assert_eq!(
        monitor
            .snapshot(Duration::from_millis(250))
            .distance_estimate_m,
        None
    );
    monitor.receive(observation(2, 0.26, -59));
    assert_eq!(
        monitor
            .snapshot(Duration::from_millis(500))
            .distance_estimate_m,
        Some(1.0)
    );
}

#[test]
fn recovery_resets_trend_instead_of_connecting_across_a_gap() {
    let mut monitor = monitor();
    for index in 0..40 {
        monitor.receive(observation(index, f64::from(index) * 0.2, -59));
    }
    assert_eq!(
        monitor.snapshot(Duration::from_secs(14)).state,
        ConnectionState::Lost
    );
    monitor.receive(observation(100, 14.1, -59));
    let snapshot = monitor.snapshot(Duration::from_secs_f64(14.1));
    assert_eq!(snapshot.state, ConnectionState::Live);
    assert_eq!(snapshot.distance_estimate_m, None);
    assert_eq!(snapshot.radial_speed_estimate_m_s, None);
    assert_eq!(snapshot.counters.signal_resets, 1);
}
