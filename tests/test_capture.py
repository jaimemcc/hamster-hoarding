import csv

from hamster_hoarding.config import CameraSettings, Settings, load_settings
from hamster_hoarding.service import CaptureService


def test_default_config_loads():
    settings = load_settings()
    assert [c.name for c in settings.cameras] == ["cam1", "cam2", "cam3", "cam4"]


def test_capture_layout_and_log(tmp_path):
    settings = Settings(
        output_dir=str(tmp_path),
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
