import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hamster_hoarding.cameras.camera import Camera, create_camera
from hamster_hoarding.cameras.quality import Quality, assess
from hamster_hoarding.config import Settings
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
        """Start all cameras. Returns {camera_name: error} for those that failed."""
        errors = {}
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
        self.stop_schedule()
        for cam in self.cameras.values():
            cam.stop()
        self.cameras.clear()

    def capture_all(self) -> list[CaptureResult]:
        if self.session is None:
            self.session = Session(self.settings)
            self.session.start()
        results = []
        with self._capture_lock:
            for name, cam in self.cameras.items():
                try:
                    # require a frame newer than now (and past the auto-exposure warm-up)
                    # so a stale or unsettled one is never saved
                    newer_than = max(time.time(), cam.started_at + self.settings.warmup_seconds)
                    frame = cam.wait_for_frame(newer_than=newer_than, timeout=newer_than - time.time() + 5)
                    if frame is None:
                        raise RuntimeError(cam.error or "no frame received")
                    quality = assess(frame.image)
                    path = self.session.save_image(cam.settings, frame, quality)
                    results.append(CaptureResult(name, path, quality))
                except Exception as exc:  # noqa: BLE001 - one bad camera must not stop the rest
                    results.append(CaptureResult(name, None, None, str(exc)))
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
