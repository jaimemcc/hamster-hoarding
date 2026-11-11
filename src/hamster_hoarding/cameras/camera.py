import sys
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from hamster_hoarding.config import CameraSettings

if sys.platform == "win32":
    BACKEND = cv2.CAP_DSHOW
    # DirectShow: exposure is log2 seconds (-13 .. -1); 0.75 = auto, 0.25 = manual
    AUTO_EXPOSURE_ON, AUTO_EXPOSURE_OFF = 0.75, 0.25
    EXPOSURE_RANGE = (-13, 0)
elif sys.platform.startswith("linux"):
    BACKEND = cv2.CAP_V4L2
    # V4L2: exposure_time_absolute in 100 us units; auto-mode menu 3 = auto, 1 = manual
    AUTO_EXPOSURE_ON, AUTO_EXPOSURE_OFF = 3, 1
    EXPOSURE_RANGE = (1, 5000)
else:
    BACKEND = cv2.CAP_ANY
    AUTO_EXPOSURE_ON, AUTO_EXPOSURE_OFF = 0.75, 0.25
    EXPOSURE_RANGE = (-13, 0)


ROTATIONS = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


@dataclass
class Frame:
    image: np.ndarray  # BGR
    timestamp: float  # time.time() when received


class Camera:
    """Threaded capture that always keeps the most recent frame."""

    def __init__(self, settings: CameraSettings):
        self.settings = settings
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._frame: Frame | None = None
        self.error: str | None = None
        self.started_at = 0.0
    @property
    def name(self) -> str:
        return self.settings.name

    def _open(self) -> None:
        raise NotImplementedError

    def _read(self) -> np.ndarray | None:
        raise NotImplementedError

    def _close(self) -> None:
        pass

    def apply_controls(self) -> None:
        """Push changed exposure/gain/brightness to the device (no-op by default)."""

    def start(self) -> None:
        self.error = None
        self._open()
        self.started_at = time.time()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"cam-{self.name}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        rotation = ROTATIONS.get(self.settings.rotate)
        while not self._stop.is_set():
            try:
                image = self._read()
                if image is not None and rotation is not None:
                    image = cv2.rotate(image, rotation)
            except Exception as exc:  # noqa: BLE001 - keep thread alive; surfaced via .error
                self.error = str(exc)
                time.sleep(0.5)
                continue
            if image is None:
                time.sleep(0.05)
                continue
            with self._lock:
                self._frame = Frame(image, time.time())

    def latest(self) -> Frame | None:
        with self._lock:
            return self._frame

    def wait_for_frame(self, newer_than: float = 0.0, timeout: float = 5.0) -> Frame | None:
        """Block until a frame newer than `newer_than` arrives (avoids saving stale frames)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self.latest()
            if frame is not None and frame.timestamp > newer_than:
                return frame
            time.sleep(0.02)
        return None

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        self._close()


class OpenCVCamera(Camera):
    def __init__(self, settings: CameraSettings):
        super().__init__(settings)
        self._cap: cv2.VideoCapture | None = None
        self._cap_lock = threading.Lock()

    def _open(self) -> None:
        s = self.settings
        cap = cv2.VideoCapture(s.device, BACKEND)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Could not open {s.name} (device {s.device})")
        if s.fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*s.fourcc))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, s.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, s.height)
        self._cap = cap
        self.apply_controls()

    def apply_controls(self) -> None:
        """Push exposure/gain/brightness to the device.

        Cameras remember their last exposure mode, so the mode is always set explicitly.
        """
        if self._cap is None:
            return
        s = self.settings
        with self._cap_lock:
            if s.exposure is None:
                self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_ON)
            else:
                self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_OFF)
                self._cap.set(cv2.CAP_PROP_EXPOSURE, s.exposure)
            if s.gain is not None:
                self._cap.set(cv2.CAP_PROP_GAIN, s.gain)
            if s.brightness is not None:
                self._cap.set(cv2.CAP_PROP_BRIGHTNESS, s.brightness)
        # restart the auto-exposure warm-up window after a change
        self.started_at = time.time()

    def _read(self) -> np.ndarray | None:
        with self._cap_lock:
            ok, image = self._cap.read()
        return image if ok else None

    def _close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class MockCamera(Camera):
    """Synthetic camera for development and tests without hardware."""

    def _open(self) -> None:
        self._n = 0

    def _read(self) -> np.ndarray | None:
        time.sleep(1 / 15)
        s = self.settings
        h, w = min(s.height, 480), min(s.width, 640)
        self._n += 1
        image = np.full((h, w, 3), 110, np.uint8)
        x = (self._n * 8) % w
        cv2.circle(image, (x, h // 2), 30, (40, 200, 240), -1)
        cv2.putText(image, s.name, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        return image


def create_camera(settings: CameraSettings) -> Camera:
    if settings.device == "mock":
        return MockCamera(settings)
    return OpenCVCamera(settings)
