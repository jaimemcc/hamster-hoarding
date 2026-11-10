from dataclasses import dataclass

import cv2
import numpy as np

# Thresholds for flagging images that will be hard to use for computer vision.
MIN_BRIGHTNESS = 50
MAX_BRIGHTNESS = 200
MAX_CLIPPED_FRACTION = 0.05
MIN_SHARPNESS = 30.0


@dataclass
class Quality:
    brightness: float  # mean gray level, 0-255
    dark_fraction: float  # fraction of pixels <= 5
    bright_fraction: float  # fraction of pixels >= 250
    sharpness: float  # variance of Laplacian (higher = sharper)

    @property
    def warnings(self) -> list[str]:
        out = []
        if self.brightness < MIN_BRIGHTNESS:
            out.append("too dark")
        if self.brightness > MAX_BRIGHTNESS:
            out.append("too bright")
        if self.dark_fraction > MAX_CLIPPED_FRACTION:
            out.append("shadows clipped")
        if self.bright_fraction > MAX_CLIPPED_FRACTION:
            out.append("highlights clipped")
        if self.sharpness < MIN_SHARPNESS:
            out.append("blurry/low detail")
        return out

    @property
    def ok(self) -> bool:
        return not self.warnings


def assess(image: np.ndarray) -> Quality:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return Quality(
        brightness=float(gray.mean()),
        dark_fraction=float((gray <= 5).mean()),
        bright_fraction=float((gray >= 250).mean()),
        sharpness=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
    )
