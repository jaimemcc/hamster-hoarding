import csv
import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import cv2

from hamster_hoarding.cameras.camera import Frame
from hamster_hoarding.cameras.quality import Quality
from hamster_hoarding.config import CameraSettings, Settings

BASE_COLUMNS = ["timestamp", "camera"]
QUALITY_COLUMNS = [
    "file",
    "brightness",
    "dark_fraction",
    "bright_fraction",
    "sharpness",
    "warnings",
]


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "-", str(value)).strip("-")


class Session:
    """On-disk layout:

    <output_dir>/<session_id>/
        session.json     settings snapshot + start time
        captures.csv     one row per image: time, camera, metadata fields, file, quality
        <camera>/<camera>[_<filename metadata>]_<YYYYmmddTHHMMSS>.jpg
    """

    def __init__(self, settings: Settings, session_id: str | None = None):
        self.settings = settings
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.root = Path(settings.output_dir) / self.session_id
        self.log_path = self.root / "captures.csv"
        self.columns = BASE_COLUMNS + settings.metadata_fields + QUALITY_COLUMNS

    def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        meta = {
            "session_id": self.session_id,
            "started": datetime.now().astimezone().isoformat(timespec="seconds"),
            "settings": asdict(self.settings),
        }
        meta_path = self.root / "session.json"
        if not meta_path.exists():
            meta_path.write_text(json.dumps(meta, indent=2))
        if self.log_path.exists():
            self._migrate_columns()
        else:
            with self.log_path.open("w", newline="") as f:
                csv.writer(f).writerow(self.columns)

    def _migrate_columns(self) -> None:
        """Resuming an existing session: keep its columns, appending any new metadata fields."""
        with self.log_path.open(newline="") as f:
            rows = list(csv.reader(f))
        existing = rows[0] if rows else []
        missing = [c for c in self.columns if c not in existing]
        self.columns = existing + missing
        if missing or not rows:
            with self.log_path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)
                writer.writerows(r + [""] * len(missing) for r in rows[1:])

    def images(self, camera: str) -> list[Path]:
        """Existing images for a camera in capture order (from the log)."""
        if not self.log_path.exists():
            return []
        with self.log_path.open(newline="") as f:
            rows = csv.DictReader(f)
            paths = [self.root / r["file"] for r in rows if r.get("camera") == camera]
        return [p for p in paths if p.exists()]

    def save_image(self, camera: CameraSettings, frame: Frame, quality: Quality) -> Path:
        when = datetime.fromtimestamp(frame.timestamp).astimezone()
        name = camera.name
        parts = [name]
        parts += [
            _safe(camera.metadata[k])
            for k in self.settings.filename_fields
            if camera.metadata.get(k)
        ]
        parts.append(f"{when:%Y%m%dT%H%M%S}")
        folder = self.root / name
        folder.mkdir(exist_ok=True)
        path = folder / ("_".join(parts) + ".jpg")
        ok = cv2.imwrite(
            str(path), frame.image, [cv2.IMWRITE_JPEG_QUALITY, self.settings.jpeg_quality]
        )
        if not ok:
            raise OSError(f"Failed to write {path}")
        row = {
            "timestamp": when.isoformat(timespec="seconds"),
            "camera": name,
            "file": path.relative_to(self.root).as_posix(),
            "brightness": f"{quality.brightness:.1f}",
            "dark_fraction": f"{quality.dark_fraction:.4f}",
            "bright_fraction": f"{quality.bright_fraction:.4f}",
            "sharpness": f"{quality.sharpness:.1f}",
            "warnings": ";".join(quality.warnings),
        }
        row.update({k: camera.metadata.get(k, "") for k in self.settings.metadata_fields})
        with self.log_path.open("a", newline="") as f:
            csv.DictWriter(f, self.columns, extrasaction="ignore").writerow(row)
        return path
