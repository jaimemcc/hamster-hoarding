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
                    # require a frame newer than now so a stale one is never saved
                    frame = cam.wait_for_frame(newer_than=time.time())
                    if frame is None:
                        raise RuntimeError(cam.error or "no frame received")
                    quality = assess(frame.image)
                    path = self.session.save_image(name, frame, quality)
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

    def start_schedule(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="schedule", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.capture_all()
            if self._stop.wait(self.settings.interval_minutes * 60):
                break

    def stop_schedule(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
