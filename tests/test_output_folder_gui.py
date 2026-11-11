import csv
import time

import pytest

from hamster_hoarding.config import CameraSettings, Settings, load_settings


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from hamster_hoarding.gui import main_window

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "LAST_USED_CONFIG", tmp_path / "last_used.yaml")
    settings = Settings(
        output_dir=str(tmp_path / "original"),
        live_preview=False,
        load_last_saved=True,
        warmup_seconds=0,
        cameras=[CameraSettings(name="cam1", device="mock")],
    )
    win = main_window.MainWindow(settings)
    yield win, app
    win.close()


def wait_for_capture(win, app):
    deadline = time.monotonic() + 10
    while not win.capture_btn.isEnabled() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert win.capture_btn.isEnabled()


def test_choose_folder_and_keep_sessions_separate(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from hamster_hoarding.gui.main_window import MainWindow

    win, app = window
    win.session_edit.setText("experiment")
    win.note_edit.setText("old location")
    win.add_note()
    old_session = win.service.session
    chosen = tmp_path / "new folder"
    chosen.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(chosen))

    win.choose_output_folder()
    assert win.settings.output_dir == str(chosen)
    assert win.output_label.text() == str(chosen)
    assert win.service.session is None
    assert win.settings.last_session is None
    assert not win.resume_session_btn.isEnabled()
    assert old_session.root == tmp_path / "original" / "experiment"

    win.note_edit.setText("added food")
    win.add_note()
    win.capture_now()
    assert not win.output_btn.isEnabled()
    wait_for_capture(win, app)
    assert win.output_btn.isEnabled()
    root = chosen / "experiment"
    assert list((root / "cam1").glob("*.jpg"))
    with (root / "notes.csv").open(encoding="utf-8", newline="") as f:
        assert [row["note"] for row in csv.DictReader(f)] == ["added food"]
    win._save_state()
    restored = load_settings(tmp_path / "last_used.yaml")
    assert restored.output_dir == str(chosen)
    assert restored.last_session == "experiment"
    restarted = MainWindow(restored)
    try:
        assert restarted.output_label.text() == str(chosen)
        assert restarted.resume_session_btn.isEnabled()
        restarted.resume_last_session()
        assert restarted.service.session.root == root
        assert len(restarted.tiles["cam1"].history) == 1
    finally:
        restarted.close()


def test_cancel_same_folder_and_schedule_protect_active_session(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    win, app = window
    win.session_edit.setText("existing")
    win.add_note()  # blank notes do not create a session
    win._ensure_session()
    session = win.service.session
    session.root.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: "")
    win.choose_output_folder()
    assert win.service.session is session
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: str(session.root.parent.resolve())
    )
    win.choose_output_folder()
    assert win.service.session is session
    assert win.settings.last_session == "existing"

    win.start_schedule()
    assert not win.output_btn.isEnabled()
    win.toggle_pause()
    assert not win.output_btn.isEnabled()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path))
    win.choose_output_folder()
    assert win.service.session is session
    win.stop_schedule()
    app.processEvents()
    assert win.output_btn.isEnabled()
