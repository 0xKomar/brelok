import random
import unittest

from trend_detector import DepartureTrendDetector


class DepartureTrendDetectorTests(unittest.TestCase):
    def test_consistent_departure_triggers(self):
        detector = DepartureTrendDetector(window_seconds=5)
        result = None
        for index in range(51):
            result = detector.add(-55 - index * 0.2, timestamp=index * 0.1)
        self.assertTrue(result.triggered)
        self.assertLess(result.slope_db_per_second, -1.5)
        self.assertGreaterEqual(result.rssi_drop, 4)

    def test_stable_noisy_signal_does_not_trigger(self):
        detector = DepartureTrendDetector(window_seconds=5)
        randomizer = random.Random(42)
        result = None
        for index in range(51):
            result = detector.add(-60 + randomizer.uniform(-1.5, 1.5), timestamp=index * 0.1)
        self.assertFalse(result.triggered)
        self.assertLess(result.confidence, 1)

    def test_single_signal_drop_does_not_trigger(self):
        detector = DepartureTrendDetector(window_seconds=5)
        result = None
        for index in range(51):
            rssi = -80 if index == 25 else -58
            result = detector.add(rssi, timestamp=index * 0.1)
        self.assertFalse(result.triggered)

    def test_moving_closer_does_not_trigger(self):
        detector = DepartureTrendDetector(window_seconds=3)
        result = None
        for index in range(31):
            result = detector.add(-80 + index * 0.4, timestamp=index * 0.1)
        self.assertFalse(result.triggered)
        self.assertGreater(result.slope_db_per_second, 0)

    def test_reset_discards_previous_departure(self):
        detector = DepartureTrendDetector(window_seconds=2)
        for index in range(11):
            detector.add(-55 - index, timestamp=index * 0.1)
        detector.reset()
        result = detector.add(-70, timestamp=10)
        self.assertEqual(result.sample_count, 1)
        self.assertFalse(result.triggered)


if __name__ == "__main__":
    unittest.main()
