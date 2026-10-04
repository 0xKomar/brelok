import unittest

from telemetry_protocol import PacketError, decode_telemetry, normalize_device_id

# Same literal vector as firmware-esp32/tests/firmware_tests.cpp:testPacket.
GOLDEN_HEX = "0201123456789ABC3412EFCDAB89177B00C8011503A00FFD"
GOLDEN = bytes.fromhex(GOLDEN_HEX)


def packet(sequence=1, boot=0x1234, **changes):
    from dataclasses import replace
    return replace(decode_telemetry(GOLDEN), sequence=sequence, boot_id=boot, **changes)


class TelemetryProtocolTests(unittest.TestCase):
    def test_firmware_golden_vector_byte_order_and_units(self):
        decoded = decode_telemetry(GOLDEN)
        self.assertEqual(decoded.device_id, "123456789ABC")
        self.assertEqual(decoded.protocol_version, 2)
        self.assertEqual(decoded.boot_id, 0x1234)
        self.assertEqual(decoded.sequence, 0x89ABCDEF)
        self.assertEqual(decoded.flags, 0x17)
        self.assertTrue(decoded.moving)
        self.assertEqual(decoded.acceleration_rms_mg, 123)
        self.assertEqual(decoded.gyro_rms_dps, 45.6)
        self.assertEqual(decoded.motion_age_ms, 789)
        self.assertEqual(decoded.battery_mv, 4000)
        self.assertEqual(decoded.nominal_tx_dbm, -3)

    def test_v1_radio_only_and_foreign_protocols(self):
        decoded = decode_telemetry(bytes.fromhex("0101A1B2C3D4E5F6"))
        self.assertEqual(decoded.device_id, "A1B2C3D4E5F6")
        self.assertIsNone(decoded.sequence)
        self.assertIsNone(decoded.moving)
        self.assertIsNone(decoded.battery_mv)
        for payload in (b"", b"\x02", b"\x04\x01", b"\x02\x04" + GOLDEN[2:]):
            self.assertIsNone(decode_telemetry(payload))

    def test_v3_touch_marker_and_counter(self):
        raw = bytearray(GOLDEN)
        raw[0] = 3
        raw[14] |= 1 << 5
        raw[23] = 42
        decoded = decode_telemetry(raw)
        self.assertEqual(decoded.protocol_version, 3)
        self.assertTrue(decoded.button_event_active)
        self.assertEqual(decoded.button_event_count, 42)
        self.assertEqual(decoded.nominal_tx_dbm, 3)

    def test_rejects_truncation_and_extra_bytes(self):
        for length in range(2, 24):
            with self.subTest(length=length), self.assertRaises(PacketError):
                decode_telemetry(GOLDEN[:length])
        with self.assertRaises(PacketError):
            decode_telemetry(GOLDEN + b"\x00")
        with self.assertRaises(PacketError):
            decode_telemetry(b"\x01\x01")

    def test_invalid_sensors_are_unknown_instead_of_zero(self):
        raw = bytearray(GOLDEN)
        raw[14] = 0x08  # Clipping; all valid bits clear.
        raw[15:19] = b"\x00" * 4
        raw[19:21] = b"\xFF\xFF"
        raw[21:23] = b"\x00\x00"
        decoded = decode_telemetry(raw)
        self.assertTrue(decoded.clipped)
        self.assertFalse(decoded.imu_valid)
        self.assertIsNone(decoded.moving)
        self.assertIsNone(decoded.acceleration_rms_mg)
        self.assertIsNone(decoded.gyro_rms_dps)
        self.assertIsNone(decoded.motion_age_ms)
        self.assertIsNone(decoded.battery_mv)

    def test_age_unknown_and_saturated_are_distinct(self):
        for age, expected, saturated in ((65535, None, False), (65534, 65534, True), (0, 0, False)):
            raw = bytearray(GOLDEN)
            raw[19:21] = age.to_bytes(2, "little")
            decoded = decode_telemetry(raw)
            self.assertEqual(decoded.motion_age_ms, expected)
            self.assertEqual(decoded.motion_age_saturated, saturated)

    def test_accelerometer_is_usable_without_gyro(self):
        raw = bytearray(GOLDEN)
        raw[14] &= ~4
        raw[17:19] = b"\x00\x00"
        decoded = decode_telemetry(raw)
        self.assertTrue(decoded.imu_valid)
        self.assertFalse(decoded.gyro_valid)
        self.assertIsNone(decoded.gyro_rms_dps)

    def test_rejects_reserved_flags_and_contradictions(self):
        mutations = ((14, 0x97), (14, 0x15), (14, 0x1F), (14, 0x13),
                     (14, 0x07), (22, 0))
        for offset, value in mutations:
            raw = bytearray(GOLDEN)
            raw[offset] = value
            with self.subTest(offset=offset, value=value), self.assertRaises(PacketError):
                decode_telemetry(raw)

    def test_hardware_id_does_not_accept_platform_uuid_or_name(self):
        self.assertEqual(normalize_device_id("a1:b2:c3:d4:e5:f6"), "A1B2C3D4E5F6")
        self.assertEqual(normalize_device_id("A1-B2-C3-D4-E5-F6"), "A1B2C3D4E5F6")
        for value in ("breLock", "12345", "GG123456789A", "123E4567-E89B-12D3-A456-426614174000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_device_id(value)


if __name__ == "__main__":
    unittest.main()
