import unittest

import numpy as np

import auto_flask


class AutoFlaskTests(unittest.TestCase):
    def test_resource_colour_counts_use_separate_globes(self):
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        image[78:99, 1:15] = (150, 20, 20)
        image[78:99, 185:199] = (20, 55, 150)
        self.assertGreater(auto_flask.resource_color_count(image, "life"), 100)
        self.assertGreater(auto_flask.resource_color_count(image, "mana"), 100)

    def test_roi_boxes_stay_on_opposite_hud_edges(self):
        life = auto_flask.resource_roi_box((1920, 1080), "life")
        mana = auto_flask.resource_roi_box((1920, 1080), "mana")
        self.assertLess(life[2], 200)
        self.assertGreater(mana[0], 1700)

    def test_relative_meter_treats_calibrated_available_amount_as_full(self):
        meter = auto_flask.RelativeGlobeMeter(calibration_frames=3, smoothing_frames=1)
        self.assertIsNone(meter.feed(500))
        self.assertIsNone(meter.feed(510))
        self.assertAlmostEqual(meter.feed(505), 100.0, delta=2.0)
        self.assertAlmostEqual(meter.feed(250), 49.5, delta=2.0)

    def test_trigger_confirms_and_respects_cooldown(self):
        trigger = auto_flask.ThresholdTrigger(90, 0.8, confirmation_frames=2)
        self.assertFalse(trigger.feed(85, now=1.0))
        self.assertTrue(trigger.feed(84, now=1.1))
        self.assertFalse(trigger.feed(80, now=1.2))
        self.assertTrue(trigger.feed(80, now=2.0))

    def test_trigger_resets_confirmation_after_recovery(self):
        trigger = auto_flask.ThresholdTrigger(90, 0.5, confirmation_frames=2)
        self.assertFalse(trigger.feed(85, now=1.0))
        self.assertFalse(trigger.feed(95, now=1.1))
        self.assertFalse(trigger.feed(85, now=1.2))


if __name__ == "__main__":
    unittest.main()
