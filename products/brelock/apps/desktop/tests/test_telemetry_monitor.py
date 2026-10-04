import math
import unittest

from telemetry_monitor import DeviceMonitor, MonitorConfig
from telemetry_protocol import decode_telemetry
from test_telemetry_protocol import packet


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.monitor = DeviceMonitor("123456789ABC")

    def feed(self, rssi, samples=36, interval=0.2, offset=100000.0):
        for index in range(samples):
            at = offset + index * interval
            self.monitor.receive(packet(index), rssi(at - offset), at)
        return at

    def test_never_seen_is_waiting_not_lost_or_stationary(self):
        snapshot = self.monitor.snapshot(100)
        self.assertEqual(snapshot["status"], "WAITING")
        self.assertIsNone(snapshot["packet_age_s"])
        self.assertEqual(snapshot["motion"], "unknown")
        self.assertIsNone(snapshot["distance_estimate_m"])

    def test_distance_requires_two_real_buckets_and_uses_reference_model(self):
        self.monitor.receive(packet(1), -59, 0.0)
        self.assertIsNone(self.monitor.snapshot(0.25)["distance_estimate_m"])
        self.monitor.receive(packet(2), -59, 0.26)
        snapshot = self.monitor.snapshot(0.5)
        self.assertAlmostEqual(snapshot["distance_estimate_m"], 1.0)
        self.assertEqual(snapshot["rssi_filtered_dbm"], -59)
        self.assertIsNone(snapshot["actual_speed_m_s"])

    def test_median_rejects_single_weak_outlier(self):
        at = self.feed(lambda elapsed: -110 if 2.4 <= elapsed < 2.6 else -59)
        self.assertAlmostEqual(self.monitor.snapshot(at + 0.1)["rssi_filtered_dbm"], -59)

    def test_monotonic_fall_has_positive_radial_estimate_and_high_fit(self):
        at = self.feed(lambda elapsed: -55 - 3 * elapsed)
        snapshot = self.monitor.snapshot(at + 0.1)
        self.assertEqual(snapshot["trend"]["quality"], "valid")
        self.assertAlmostEqual(snapshot["trend"]["slope_db_s"], -3, delta=0.2)
        self.assertGreater(snapshot["trend"]["r_squared"], 0.98)
        self.assertGreater(snapshot["radial_speed_estimate_m_s"], 0)

    def test_signal_rising_has_negative_radial_estimate(self):
        at = self.feed(lambda elapsed: -85 + 3 * elapsed)
        self.assertLess(self.monitor.snapshot(at + 0.1)["radial_speed_estimate_m_s"], 0)

    def test_stable_signal_does_not_invent_a_reliable_velocity(self):
        at = self.feed(lambda _: -59)
        snapshot = self.monitor.snapshot(at + 0.1)
        self.assertEqual(snapshot["trend"]["quality"], "no_clear_trend")
        self.assertIsNone(snapshot["trend"]["r_squared"])
        self.assertIsNone(snapshot["radial_speed_estimate_m_s"])

    def test_sparse_window_cannot_produce_velocity(self):
        at = self.feed(lambda elapsed: -55 - 3 * elapsed, samples=15, interval=0.6)
        snapshot = self.monitor.snapshot(at + 0.1)
        self.assertNotEqual(snapshot["trend"]["quality"], "valid")
        self.assertIsNone(snapshot["radial_speed_estimate_m_s"])

    def test_duplicate_flood_cannot_refresh_sensors_or_heartbeat(self):
        first = packet(1)
        self.monitor.receive(first, -59, 0)
        for index in range(1, 21):
            self.assertEqual(self.monitor.receive(first, -60, index / 10), "duplicate")
        stale = self.monitor.snapshot(2)
        self.assertEqual(stale["status"], "STALE")
        self.assertIsNone(stale["rssi_raw_dbm"])
        self.assertFalse(stale["imu_valid"])
        self.assertIsNone(stale["battery_mv"])
        for index in range(21, 70):
            self.assertEqual(self.monitor.receive(first, -60, index / 10), "duplicate")
        self.assertEqual(self.monitor.snapshot(6.9)["status"], "LOST")
        self.assertEqual(self.monitor.counts["new_packets"], 1)
        self.assertEqual(self.monitor.counts["duplicates"], 69)
        self.assertEqual(self.monitor.last_packet_at, 0)

    def test_out_of_order_and_conflicting_duplicate_do_not_replace_latest(self):
        self.monitor.receive(packet(10), -60, 0)
        self.assertEqual(self.monitor.receive(packet(9), -90, 1), "out_of_order")
        self.assertEqual(self.monitor.receive(packet(10, battery_mv=3900), -90, 1.1), "conflict")
        self.assertEqual(self.monitor.last_rssi, -60)
        self.assertEqual(self.monitor.last_packet_at, 0)
        self.assertEqual(self.monitor.packet.battery_mv, 4000)

    def test_wrap_and_missing_summaries(self):
        self.monitor.receive(packet(0xFFFFFFFE), -60, 0)
        self.assertEqual(self.monitor.receive(packet(0), -60, 0.2), "new")
        self.assertEqual(self.monitor.counts["skipped_summaries"], 1)
        self.assertEqual(self.monitor.receive(packet(3), -60, 0.4), "new")
        self.assertEqual(self.monitor.counts["skipped_summaries"], 3)
        self.assertEqual(self.monitor.counts["new_packets"], 3)

    def test_reboot_resets_signal_and_late_old_boot_cannot_change_epoch(self):
        at = self.feed(lambda elapsed: -55 - 3 * elapsed, offset=0)
        self.assertIsNotNone(self.monitor.snapshot(at + 0.1)["radial_speed_estimate_m_s"])
        self.assertEqual(self.monitor.receive(packet(0, boot=5678), -55, at + 0.2), "reboot")
        self.assertIsNone(self.monitor.snapshot(at + 0.2)["distance_estimate_m"])
        self.assertEqual(self.monitor.receive(packet(99), -90, at + 0.3), "old_boot")
        self.assertEqual(self.monitor.packet.boot_id, 5678)
        self.assertEqual(self.monitor.counts["reboots"], 1)

    def test_recovery_after_gap_does_not_reuse_pre_gap_trend(self):
        at = self.feed(lambda elapsed: -55 - 3 * elapsed)
        lost = self.monitor.snapshot(at + 6)
        self.assertEqual(lost["status"], "LOST")
        self.assertIsNone(lost["radial_speed_estimate_m_s"])
        self.monitor.receive(packet(100), -59, at + 6.1)
        recovery = self.monitor.snapshot(at + 6.1)
        self.assertEqual(recovery["status"], "LIVE")
        self.assertIsNone(recovery["distance_estimate_m"])
        self.assertEqual(self.monitor.counts["signal_resets"], 1)

    def test_new_telemetry_with_missing_radio_does_not_reuse_old_rssi(self):
        self.monitor.receive(packet(1), -59, 0)
        for index in range(2, 12):
            self.monitor.receive(packet(index), 127, index * 0.2)
        snapshot = self.monitor.snapshot(2.3)
        self.assertEqual(snapshot["status"], "LIVE")
        self.assertTrue(snapshot["imu_valid"])
        self.assertIsNone(snapshot["rssi_raw_dbm"])
        self.assertIsNone(snapshot["distance_estimate_m"])
        self.assertEqual(self.monitor.counts["invalid_rssi"], 10)

    def test_sensor_unknown_saturated_age_and_units(self):
        self.monitor.receive(packet(1, motion_age_ms=65534, motion_age_saturated=True), -60, 0)
        snapshot = self.monitor.snapshot(0.5)
        self.assertAlmostEqual(snapshot["motion_age_s"], 66.034)
        self.assertTrue(snapshot["motion_age_saturated"])
        self.assertFalse(snapshot["recent_motion"])
        self.assertAlmostEqual(snapshot["acceleration_rms_m_s2"], 1.20621795)
        self.monitor.receive(packet(2, imu_valid=False, gyro_valid=False, moving=None,
                                    acceleration_rms_mg=None, gyro_rms_dps=None, motion_age_ms=None), -60, 0.6)
        self.assertEqual(self.monitor.snapshot(0.7)["motion"], "unknown")

    def test_foreign_device_does_not_refresh_selected_keyfob(self):
        self.assertEqual(self.monitor.receive(packet(1, device_id="AABBCCDDEEFF"), -59, 0), "foreign")
        self.assertEqual(self.monitor.snapshot(1)["status"], "WAITING")
        self.assertEqual(self.monitor.counts["callbacks"], 0)

    def test_legacy_does_not_claim_fresh_telemetry_or_new_packet_rate(self):
        legacy = decode_telemetry(bytes.fromhex("0101123456789ABC"))
        self.monitor.receive(legacy, -59, 0)
        self.monitor.receive(legacy, -59, 0.3)
        snapshot = self.monitor.snapshot(0.6)
        self.assertEqual(snapshot["status"], "LEGACY")
        self.assertTrue(snapshot["radio_fresh"])
        self.assertFalse(snapshot["telemetry_fresh"])
        self.assertIsNone(snapshot["packet_hz"])
        self.assertIsNone(snapshot["gyro_rms_dps"])

    def test_filter_is_independent_of_number_of_identical_duplicates(self):
        other = DeviceMonitor(self.monitor.device_id)
        for index in range(40):
            at = index * 0.2
            current = packet(index)
            rssi = -55 - at
            self.monitor.receive(current, rssi, at)
            other.receive(current, rssi, at)
            for _ in range(30):
                other.receive(current, rssi, at)
        first, repeated = self.monitor.snapshot(at + 0.1), other.snapshot(at + 0.1)
        self.assertEqual(first["rssi_filtered_dbm"], repeated["rssi_filtered_dbm"])
        self.assertEqual(first["trend"], repeated["trend"])
        self.assertEqual(first["packet_hz"], repeated["packet_hz"])

    def test_configuration_rejects_nonfinite_and_invalid_thresholds(self):
        for kwargs in ({"path_loss_exponent": 0}, {"reference_rssi_dbm": math.nan},
                       {"lost_seconds": 1}, {"ema_tau_seconds": math.inf}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MonitorConfig(**kwargs)


if __name__ == "__main__":
    unittest.main()
