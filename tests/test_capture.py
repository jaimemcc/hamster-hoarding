import csv
import time

from hamster_hoarding.config import CameraSettings, Settings, load_settings
from hamster_hoarding.service import CaptureService


def test_default_config_loads():
    settings = load_settings()
    assert [c.name for c in settings.cameras] == ["cam1", "cam2", "cam3", "cam4"]
    assert settings.cameras[0].metadata["animal_id"] == "H01"


def test_metadata_in_filename_and_csv(tmp_path):
    settings = Settings(
        output_dir=str(tmp_path),
        warmup_seconds=0,
        metadata_fields=["animal_id", "cage"],
        filename_fields=["animal_id"],
        cameras=[CameraSettings(name="cam1", device="mock", metadata={"animal_id": "H 07"})],
    )
    service = CaptureService(settings)
    service.open_cameras()
    try:
        service.new_session("m")
        service.capture_all()
    finally:
        service.close_cameras()
    (image,) = (tmp_path / "m" / "cam1").glob("*.jpg")
    assert image.name.startswith("cam1_H-07_")
    (row,) = csv.DictReader((tmp_path / "m" / "captures.csv").open())
    assert row["animal_id"] == "H 07" and row["cage"] == ""


def test_pause_skips_scheduled_captures(tmp_path):
    settings = Settings(
        output_dir=str(tmp_path),
        warmup_seconds=0,
        interval_minutes=0.02,
        cameras=[CameraSettings(name="cam1", device="mock")],
    )
    service = CaptureService(settings)
    service.open_cameras()
    service.new_session("p")
    try:
        service.start_schedule()
        time.sleep(1.5)
        service.pause()
        time.sleep(0.5)
        count = len(list((tmp_path / "p" / "cam1").glob("*.jpg")))
        time.sleep(2.5)  # > 2 intervals while paused
        assert len(list((tmp_path / "p" / "cam1").glob("*.jpg"))) == count
        service.resume()
        time.sleep(1.5)
        assert len(list((tmp_path / "p" / "cam1").glob("*.jpg"))) > count
    finally:
        service.close_cameras()


def test_capture_layout_and_log(tmp_path):
    settings = Settings(
        output_dir=str(tmp_path),
        warmup_seconds=0,
        cameras=[CameraSettings(name=f"cam{i}", device="mock") for i in (1, 2)],
    )
    service = CaptureService(settings)
    assert service.open_cameras() == {}
    try:
        service.new_session("test")
        results = service.capture_all()
    finally:
        service.close_cameras()

    assert all(r.error is None for r in results)
    root = tmp_path / "test"
    for cam in ("cam1", "cam2"):
        files = list((root / cam).glob(f"{cam}_*.jpg"))
        assert len(files) == 1
    rows = list(csv.DictReader((root / "captures.csv").open()))
    assert {r["camera"] for r in rows} == {"cam1", "cam2"}
    assert (root / "session.json").exists()
