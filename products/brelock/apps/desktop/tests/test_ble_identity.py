import unittest

from ble_identity import decode_brelock_identity


class Advertisement:
    def __init__(self, manufacturer_data):
        self.manufacturer_data = manufacturer_data


class BleIdentityTests(unittest.TestCase):
    def test_decodes_full_48_bit_identifier(self):
        advertisement = Advertisement({0xFFFF: bytes([1, 1, 0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6])})
        identity = decode_brelock_identity(advertisement)
        self.assertEqual(identity.device_id, "A1B2C3D4E5F6")

    def test_rejects_unknown_protocol_and_short_payload(self):
        self.assertIsNone(decode_brelock_identity(Advertisement({0xFFFF: bytes([2, 1])})))
        self.assertIsNone(decode_brelock_identity(Advertisement({})))


if __name__ == "__main__":
    unittest.main()
