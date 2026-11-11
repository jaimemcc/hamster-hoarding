import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hamster_hoarding.cameras.camera import Camera, Frame, create_camera
from hamster_hoarding.cameras.quality import Quality, assess
from hamster_hoarding.config import CameraSettings, Settings
from hamster_hoarding.storage import Session


@dataclass
class CaptureResult:
    camera: str
    path: Path | None
    quality: Quality | None
    error: str | None = None


class CaptureService:
    """Owns the cameras and takes timed stills; independent of any GUI."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.cameras: dict[str, Camera] = {}
        self.session: Session | None = None
        self.on_results: Callable[[list[CaptureResult]], None] | None = None
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture_lock = threading.Lock()

    def open_cameras(self) -> dict[str, str]:
        """Start all cameras (live preview). Returns {camera_name: error} for failures."""
        errors = {}
        with self._capture_lock:
            for cs in self.settings.cameras:
                if cs.name in self.cameras:
                    continue
                cam = create_camera(cs)
                try:
                    cam.start()
                except Exception as exc:  # noqa: BLE001 - report per-camera failure, keep going
                    errors[cs.name] = str(exc)
                    continue
                self.cameras[cs.name] = cam
        return errors

    def close_cameras(self) -> None:
        """Stop all streams. Captures still work: cameras are then opened one at a time."""
        with self._capture_lock:
            for cam in self.cameras.values():
                cam.stop()
            self.cameras.clear()

    def shutdown(self) -> None:
        self.stop_schedule()
        self.close_cameras()

    def _grab(self, cs: CameraSettings) -> tuple[Frame, Quality]:
        """Get one settled frame, opening the camera just for this shot if it isn't streaming."""
        cam = self.cameras.get(cs.name)
        temporary = cam is None
        if temporary:
            cam = create_camera(cs)
            cam.start()
        try:
            # require a frame newer than now (and past the auto-exposure warm-up)
            # so a stale or unsettled one is never saved
            newer_than = max(time.time(), cam.started_at + self.settings.warmup_seconds)
            timeout = newer_than - time.time() + 5
            frame = cam.wait_for_frame(newer_than=newer_than, timeout=timeout)
            if frame is None:
                raise RuntimeError(cam.error or "no frame received")
            return frame, assess(frame.image)
        finally:
            if temporary:
                cam.stop()

    def capture_all(self) -> list[CaptureResult]:
        """Capture every configured camera, one after another (never in parallel)."""
        if self.session is None:
            self.session = Session(self.settings)
            self.session.start()
        results = []
        with self._capture_lock:
            for cs in self.settings.cameras:
                try:
                    frame, quality = self._grab(cs)
                    path = self.session.save_image(cs, frame, quality)
                    results.append(CaptureResult(cs.name, path, quality))
                except Exception as exc:  # noqa: BLE001 - one bad camera must not stop the rest
                    results.append(CaptureResult(cs.name, None, None, str(exc)))
        if self.on_results:
            self.on_results(results)
        return results

    def new_session(self, session_id: str | None = None) -> Session:
        self.session = Session(self.settings, session_id)
        self.session.start()
        return self.session

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def start_schedule(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._paused.clear()
        self._wake.clear()
        self._thread = threading.Thread(target=self._loop, name="schedule", daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """Suspend scheduled captures (e.g. during feeding). Manual capture still works."""
        self._paused.set()

    def resume(self) -> None:
        """Resume scheduled captures; takes an image right away, then continues on interval."""
        self._paused.clear()
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            if not self._paused.is_set():
                self.capture_all()
            deadline = time.monotonic() + self.settings.interval_minutes * 60
            while not self._stop.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if self._wake.wait(min(remaining, 1.0)):
                    self._wake.clear()
                    deadline = 0  # resumed: capture immediately
                    break

    def stop_schedule(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
