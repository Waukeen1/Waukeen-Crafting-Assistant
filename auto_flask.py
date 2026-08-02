"""Screen-based Life and Mana monitoring for the Auto Flask mode."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import statistics
import time

import numpy as np


RESOURCE_ROIS = {
    "life": (0.002, 0.775, 0.076, 0.995),
    "mana": (0.924, 0.775, 0.998, 0.995),
}


def _rgb_array(image):
    array = np.asarray(image.convert("RGB") if hasattr(image, "convert") else image)
    if array.ndim != 3 or array.shape[2] < 3:
        raise ValueError("Expected an RGB image")
    return array[:, :, :3].astype(np.int16, copy=False)


def resource_roi_box(size, resource: str):
    if resource not in RESOURCE_ROIS:
        raise ValueError(f"Unknown resource: {resource}")
    width, height = (int(size[0]), int(size[1]))
    left, top, right, bottom = RESOURCE_ROIS[resource]
    return (
        max(0, int(width * left)),
        max(0, int(height * top)),
        min(width, int(width * right)),
        min(height, int(height * bottom)),
    )


def resource_color_count_crop(image, resource: str) -> int:
    """Count fluid-coloured pixels in an already-cropped globe image."""
    if resource not in RESOURCE_ROIS:
        raise ValueError(f"Unknown resource: {resource}")
    crop = _rgb_array(image)
    if crop.size == 0:
        return 0
    red, green, blue = (crop[:, :, index] for index in range(3))
    if resource == "life":
        mask = (
            (red >= 52)
            & (red - green >= 16)
            & (red - blue >= 10)
            & (red * 100 >= green * 122)
        )
    else:
        mask = (
            (blue >= 42)
            & (blue - red >= 10)
            & (blue * 100 >= red * 118)
            & (blue * 100 >= green * 88)
        )
    return int(np.count_nonzero(mask))


def resource_color_count(image, resource: str) -> int:
    """Count fluid-coloured pixels in the resource globe's HUD region."""
    rgb = _rgb_array(image)
    height, width = rgb.shape[:2]
    left, top, right, bottom = resource_roi_box((width, height), resource)
    return resource_color_count_crop(rgb[top:bottom, left:right], resource)


@dataclass
class RelativeGlobeMeter:
    """Convert colour counts to reserve-aware percentages."""

    calibration_frames: int = 12
    smoothing_frames: int = 3
    minimum_baseline: int = 80

    def __post_init__(self):
        self._calibration = []
        self._recent = deque(maxlen=max(1, int(self.smoothing_frames)))
        self.baseline = None

    @property
    def calibrated(self) -> bool:
        return self.baseline is not None

    def feed(self, pixel_count: int):
        count = max(0, int(pixel_count))
        if self.baseline is None:
            if count >= self.minimum_baseline:
                self._calibration.append(count)
            if len(self._calibration) < self.calibration_frames:
                return None
            ordered = sorted(self._calibration)
            upper_half = ordered[len(ordered) // 2 :]
            self.baseline = float(statistics.median(upper_half))
            self._recent.clear()
        elif count > self.baseline * 1.03:
            # A brighter animation frame should improve, not invalidate, calibration.
            self.baseline = float(count)

        percent = max(0.0, min(100.0, count * 100.0 / self.baseline))
        self._recent.append(percent)
        return float(statistics.median(self._recent))


@dataclass
class ThresholdTrigger:
    threshold: float
    cooldown_seconds: float
    confirmation_frames: int = 2

    def __post_init__(self):
        self._below_frames = 0
        self._last_trigger = -1e9

    def feed(self, percent, now=None) -> bool:
        if percent is None:
            self._below_frames = 0
            return False
        now = time.monotonic() if now is None else float(now)
        if float(percent) <= float(self.threshold):
            self._below_frames += 1
        else:
            self._below_frames = 0
            return False
        if self._below_frames < max(1, int(self.confirmation_frames)):
            return False
        if now - self._last_trigger < float(self.cooldown_seconds):
            return False
        self._last_trigger = now
        return True
