import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import cv2

from hamster_hoarding.cameras.camera import Frame
from hamster_hoarding.cameras.quality import Quality
from hamster_hoarding.config import Settings

LOG_COLUMNS = [
    "timestamp",
    "camera",
    "file",
    "brightness",
    "dark_fraction",
    "bright_fraction",
    "sharpness",
    "warnings",
]


class Session:
    """On-disk layout:

    <output_dir>/<session_id>/
        session.json                     settings snapshot + start time
        captures.csv                     one row per image (camera, time, quality)
        <camera_name>/<camera_name>_<YYYYmmddTHHMMSS>.jpg
    """

    def __init__(self, settings: Settings, session_id: str | None = None):
        self.settings = settings
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.root = Path(settings.output_dir) / self.session_id
        self.log_path = self.root / "captures.csv"

    def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        meta = {
            "session_id": self.session_id,
            "started": datetime.now().astimezone().isoformat(timespec="seconds"),
            "settings": asdict(self.settings),
        }
        (self.root / "session.json").write_text(json.dumps(meta, indent=2))
        if not self.log_path.exists():
            with self.log_path.open("w", newline="") as f:
                csv.writer(f).writerow(LOG_COLUMNS)

    def save_image(self, camera: str, frame: Frame, quality: Quality) -> Path:
        when = datetime.fromtimestamp(frame.timestamp).astimezone()
        folder = self.root / camera
        folder.mkdir(exist_ok=True)
        path = folder / f"{camera}_{when:%Y%m%dT%H%M%S}.jpg"
        ok = cv2.imwrite(
            str(path), frame.image, [cv2.IMWRITE_JPEG_QUALITY, self.settings.jpeg_quality]
        )
        if not ok:
            raise OSError(f"Failed to write {path}")
        with self.log_path.open("a", newline="") as f:
            csv.writer(f).writerow(
                [
                    when.isoformat(timespec="seconds"),
                    camera,
                    path.relative_to(self.root).as_posix(),
                    f"{quality.brightness:.1f}",
                    f"{quality.dark_fraction:.4f}",
                    f"{quality.bright_fraction:.4f}",
                    f"{quality.sharpness:.1f}",
                    ";".join(quality.warnings),
                ]
            )
        return path
