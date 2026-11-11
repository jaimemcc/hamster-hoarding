from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


@dataclass
class CameraSettings:
    """One physical camera.

    `name` is the stable identity used in file names and folders (e.g. "cam1");
    `device` says where to find it: an integer index, a device path such as
    /dev/v4l/by-path/... (Linux, stable per USB port), or "mock" for a synthetic camera.
    """

    name: str = "cam1"
    device: int | str = 0
    width: int = 1920
    height: int = 1080
    fourcc: str = "MJPG"
    # Optional OpenCV property overrides; None leaves the camera default / auto.
    brightness: float | None = None
    exposure: float | None = None
    gain: float | None = None
    # Values for Settings.metadata_fields, e.g. {"animal_id": "H07", "cage": "A"}
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Settings:
    output_dir: str = "data"
    interval_minutes: float = 10.0
    jpeg_quality: int = 95
    # Seconds after opening a camera before images are trusted (auto-exposure settling).
    warmup_seconds: float = 3.0
    # Per-camera metadata keys: each becomes a CSV column and editable field in the GUI.
    metadata_fields: list[str] = field(default_factory=list)
    # Subset of metadata_fields whose values are also put in the image file name.
    filename_fields: list[str] = field(default_factory=list)
    cameras: list[CameraSettings] = field(default_factory=list)


def _camera_from_dict(raw: dict) -> CameraSettings:
    known = {f.name for f in fields(CameraSettings)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"Unknown camera setting(s): {sorted(unknown)}")
    return CameraSettings(**raw)


def load_settings(path: Path = DEFAULT_CONFIG) -> Settings:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    cameras = [_camera_from_dict(c) for c in raw.pop("cameras", [])]
    return Settings(cameras=cameras, **raw)


def save_settings(settings: Settings, path: Path) -> None:
    data = {
        "output_dir": settings.output_dir,
        "interval_minutes": settings.interval_minutes,
        "jpeg_quality": settings.jpeg_quality,
        "metadata_fields": settings.metadata_fields,
        "filename_fields": settings.filename_fields,
        "cameras": [vars(c) for c in settings.cameras],
    }
    Path(path).write_text(yaml.safe_dump(data, sort_keys=False))
