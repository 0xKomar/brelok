import math
import unittest

from diagnostics import estimate_distance, format_distance, signal_quality


class DistanceEstimationTests(unittest.TestCase):
    def test_reference_rssi_means_one_metre(self):
        self.assertAlmostEqual(estimate_distance(-59, -59), 1.0)

    def test_weaker_signal_means_greater_distance(self):
        self.assertGreater(estimate_distance(-80), estimate_distance(-60))

    def test_result_is_bounded_for_chart_safety(self):
        self.assertEqual(estimate_distance(-200), 50.0)
        self.assertEqual(estimate_distance(20), 0.05)

    def test_invalid_path_loss_exponent_is_rejected(self):
        with self.assertRaises(ValueError):
            estimate_distance(-60, path_loss_exponent=0)


class PresentationTests(unittest.TestCase):
    def test_signal_quality_is_bounded(self):
        self.assertEqual(signal_quality(-120), 0)
        self.assertEqual(signal_quality(-40), 100)

    def test_distance_format_uses_centimetres_below_one_metre(self):
        self.assertEqual(format_distance(0.42), "42 cm")
        self.assertEqual(format_distance(2.25), "2.2 m")
        self.assertEqual(format_distance(math.inf), "—")


if __name__ == "__main__":
    unittest.main()
