import threading
from pathlib import Path

import cv2
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from hamster_hoarding.cameras.camera import EXPOSURE_RANGE
from hamster_hoarding.cameras.quality import assess
from hamster_hoarding.config import LAST_USED_CONFIG, CameraSettings, Settings, save_settings
from hamster_hoarding.service import CaptureResult, CaptureService

PREVIEW_SIZE = (480, 270)


class CameraTile(QGroupBox):
    step_requested = Signal(int)  # -1 = earlier capture, +1 = later

    def __init__(self, cam: CameraSettings, fields: list[str], on_changed):
        """`on_changed(name, hardware)` fires on edits; hardware=True means re-apply controls."""
        super().__init__(cam.name)
        self.cam = cam
        self._on_changed = on_changed
        self.image = QLabel("no signal")
        self.image.setFixedSize(*PREVIEW_SIZE)
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setStyleSheet("background: #222; color: #aaa;")
        self.info = QLabel(" ")
        layout = QVBoxLayout(self)
        layout.addWidget(self.image)
        layout.addWidget(self.info)

        self.history: list[Path] = []
        self.browse_index: int | None = None  # None = follow live / newest
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        self.history_label = QLabel("no captures yet")
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.prev_btn.setToolTip("Earlier capture")
        self.next_btn.setToolTip("Later capture (past the newest returns to live)")
        nav = QHBoxLayout()
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        nav.addWidget(self.history_label, 1)
        layout.addLayout(nav)
        self.prev_btn.clicked.connect(lambda: self.step_requested.emit(-1))
        self.next_btn.clicked.connect(lambda: self.step_requested.emit(1))

        lo, hi = EXPOSURE_RANGE
        self.auto_exp = QCheckBox("Auto exposure")
        self.auto_exp.setChecked(cam.exposure is None)
        self.exposure = QSpinBox()
        self.exposure.setRange(lo, hi)
        self.exposure.setValue(int(cam.exposure) if cam.exposure is not None else (lo + hi) // 2)
        self.exposure.setEnabled(cam.exposure is not None)
        self.gain = QSpinBox()
        self.gain.setRange(0, 255)
        self.gain.setValue(int(cam.gain or 0))
        self.rotate = QComboBox()
        for degrees in (0, 90, 180, 270):
            self.rotate.addItem(f"{degrees}°", degrees)
        self.rotate.setCurrentIndex(max(0, self.rotate.findData(cam.rotate)))
        self.auto_exp.toggled.connect(self._controls_changed)
        self.exposure.valueChanged.connect(self._controls_changed)
        self.gain.valueChanged.connect(self._controls_changed)
        self.rotate.currentIndexChanged.connect(self._rotate_changed)
        row = QHBoxLayout()
        row.addWidget(self.auto_exp)
        row.addWidget(QLabel("Exposure"))
        row.addWidget(self.exposure)
        row.addWidget(QLabel("Gain"))
        row.addWidget(self.gain)
        row.addWidget(QLabel("Rotate"))
        row.addWidget(self.rotate)
        layout.addLayout(row)

        form = QFormLayout()
        for key in fields:
            edit = QLineEdit(cam.metadata.get(key, ""))
            edit.textChanged.connect(lambda text, k=key: self._metadata_changed(k, text))
            form.addRow(key, edit)
        layout.addLayout(form)

    def _metadata_changed(self, key: str, text: str) -> None:
        self.cam.metadata[key] = text
        self._on_changed(self.cam.name, False)

    def _rotate_changed(self) -> None:
        self.cam.rotate = self.rotate.currentData()
        self._on_changed(self.cam.name, False)

    def _controls_changed(self) -> None:
        auto = self.auto_exp.isChecked()
        self.exposure.setEnabled(not auto)
        self.cam.exposure = None if auto else float(self.exposure.value())
        self.cam.gain = float(self.gain.value())
        self._on_changed(self.cam.name, True)

    def show_frame(self, bgr) -> None:
        """Display a BGR image (live frame or one loaded from disk) with its quality readout."""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        self.image.setPixmap(
            QPixmap.fromImage(qimg).scaled(
                self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )
        q = assess(cv2.resize(bgr, (320, 180)))
        text = f"brightness {q.brightness:.0f} | sharpness {q.sharpness:.0f}"
        if q.warnings:
            text += "  ⚠ " + ", ".join(q.warnings)
            self.info.setStyleSheet("color: #c60;")
        else:
            self.info.setStyleSheet("color: #2a2;")
        self.info.setText(text)

    def show_error(self, message: str) -> None:
        self.image.setPixmap(QPixmap())
        self.image.setText(message)

    # --- history browsing -------------------------------------------------
    def set_history(self, paths: list[Path], live: bool) -> None:
        self.history = list(paths)
        self.browse_index = None
        self._refresh_static(live)

    def add_capture(self, path: Path, live: bool) -> None:
        self.history.append(path)
        self._refresh_static(live)

    def set_live(self, live: bool) -> None:
        self._refresh_static(live)

    def step(self, delta: int, live: bool) -> None:
        if not self.history:
            return
        current = len(self.history) - 1 if self.browse_index is None else self.browse_index
        target = min(max(current + delta, 0), len(self.history) - 1)
        # stepping onto the newest image goes back to following (live view, or newest capture)
        self.browse_index = None if target == len(self.history) - 1 else target
        self._refresh_static(live)

    def _refresh_static(self, live: bool) -> None:
        """Show the selected stored image, unless the live stream is being followed."""
        n = len(self.history)
        self.prev_btn.setEnabled(n > 0 and self.browse_index != 0 and n > 1)
        self.next_btn.setEnabled(self.browse_index is not None)
        if self.browse_index is None and live:
            self.history_label.setText(f"live  ({n} captured)")
            return
        if n == 0:
            self.history_label.setText("no captures yet")
            if not live:
                self.show_error("live preview off")
            return
        index = n - 1 if self.browse_index is None else self.browse_index
        path = self.history[index]
        self.history_label.setText(f"{index + 1}/{n}  {path.name}")
        image = cv2.imread(str(path))
        if image is None:
            self.show_error(f"cannot read {path.name}")
        else:
            self.show_frame(image)


class _Bridge(QObject):
    """Moves results from worker threads onto the GUI thread."""

    results = Signal(list)
    live_changed = Signal(dict)  # {camera: error} after opening/closing streams


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.service = CaptureService(settings)
        self.setWindowTitle("Hamster Hoarding")

        self.bridge = _Bridge()
        self.bridge.results.connect(self._on_results)
        self.bridge.live_changed.connect(self._on_live_changed)
        self.service.on_results = self.bridge.results.emit

        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        grid = QGridLayout()
        self.tiles: dict[str, CameraTile] = {}
        for i, cam in enumerate(settings.cameras):
            tile = CameraTile(cam, settings.metadata_fields, self._tile_changed)
            self.tiles[cam.name] = tile
            tile.step_requested.connect(lambda delta, t=tile: t.step(delta, self.live))
            grid.addWidget(tile, i // 2, i % 2)
        root.addLayout(grid)

        controls = QHBoxLayout()
        self.session_edit = QLineEdit()
        self.session_edit.setPlaceholderText("session name (optional)")
        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.1, 1440)
        self.interval.setDecimals(1)
        self.interval.setSuffix(" min")
        self.interval.setValue(settings.interval_minutes)
        self.capture_btn = QPushButton("Capture now")
        self.resume_session_btn = QPushButton("Resume last session")
        self.start_btn = QPushButton("Start schedule")
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        self.stop_btn = QPushButton("Stop schedule")
        self.stop_btn.setEnabled(False)
        controls.addWidget(QLabel("Session:"))
        controls.addWidget(self.session_edit)
        controls.addWidget(self.resume_session_btn)
        controls.addWidget(QLabel("Interval:"))
        controls.addWidget(self.interval)
        controls.addWidget(self.capture_btn)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.stop_btn)
        root.addLayout(controls)

        self.live_check = QCheckBox("Live preview")
        self.live_check.setChecked(settings.live_preview)
        self.live_check.setToolTip(
            "On: all cameras stream continuously (use this to adjust settings).\n"
            "Off: cameras are opened one at a time only to take each capture, which\n"
            "keeps USB bandwidth free. Tiles then show the last captured image."
        )
        root.addWidget(self.live_check)
        self.load_last_check = QCheckBox("Load last saved settings on startup")
        self.load_last_check.setChecked(settings.load_last_saved)
        self.load_last_check.setToolTip(f"Settings are saved automatically to {LAST_USED_CONFIG}")
        root.addWidget(self.load_last_check)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        root.addWidget(self.log)

        self.capture_btn.clicked.connect(self.capture_now)
        self.resume_session_btn.clicked.connect(self.resume_last_session)
        self.start_btn.clicked.connect(self.start_schedule)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.stop_btn.clicked.connect(self.stop_schedule)
        self.interval.valueChanged.connect(self._interval_changed)
        self.load_last_check.toggled.connect(self._load_last_toggled)
        self.live_check.toggled.connect(self._live_toggled)

        # Debounced so typing doesn't rewrite the file on every keystroke.
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_state)
        self._update_resume_button()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_previews)
        self.timer.start(200)

        for tile in self.tiles.values():
            tile.set_live(self.live)
        if self.live:
            for name, err in self.service.open_cameras().items():
                self._log(f"{name}: {err}")
                self.tiles[name].show_error(err)

    @property
    def live(self) -> bool:
        return self.settings.live_preview

    def _live_toggled(self, checked: bool) -> None:
        self.settings.live_preview = checked
        self.live_check.setEnabled(False)  # re-enabled once the streams have opened/closed
        self._save_timer.start()

        def work():
            errors = {}
            if checked:
                errors = self.service.open_cameras()
            else:
                self.service.close_cameras()
            self.bridge.live_changed.emit(errors)

        threading.Thread(target=work, daemon=True).start()

    def _on_live_changed(self, errors: dict) -> None:
        self.live_check.setEnabled(True)
        for tile in self.tiles.values():
            tile.set_live(self.live)
        for name, err in errors.items():
            self._log(f"{name}: {err}")
            self.tiles[name].show_error(err)
        self._log("Live preview " + ("on" if self.live else "off - cameras open only while capturing"))

    def _load_history(self) -> None:
        session = self.service.session
        for name, tile in self.tiles.items():
            tile.set_history(session.images(name) if session else [], self.live)

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _tile_changed(self, name: str, hardware: bool) -> None:
        if hardware:
            cam = self.service.cameras.get(name)
            if cam is not None:
                cam.apply_controls()
        self._save_timer.start()

    def _interval_changed(self, value: float) -> None:
        self.settings.interval_minutes = value
        self._save_timer.start()

    def _load_last_toggled(self, checked: bool) -> None:
        self.settings.load_last_saved = checked
        self._save_timer.start()

    def _save_state(self) -> None:
        try:
            save_settings(self.settings, LAST_USED_CONFIG)
        except OSError as exc:
            self._log(f"Could not save settings: {exc}")

    def _update_resume_button(self) -> None:
        last = self.settings.last_session
        exists = bool(last) and (Path(self.settings.output_dir) / last).is_dir()
        self.resume_session_btn.setEnabled(exists and not self.service.running)
        self.resume_session_btn.setToolTip(f"Last session: {last}" if exists else "No previous session")

    def resume_last_session(self) -> None:
        last = self.settings.last_session
        self.session_edit.setText(last)
        self.service.new_session(last)  # appends to the existing folder and CSV
        self._log(f"Resumed session: {self.service.session.root}")
        self._load_history()

    def _refresh_previews(self) -> None:
        for name, cam in self.service.cameras.items():
            tile = self.tiles[name]
            frame = cam.latest()
            if frame is not None and tile.browse_index is None and self.live:
                tile.show_frame(frame.image)

    def _ensure_session(self) -> None:
        # A session is fixed once created; changing the name starts a new one.
        wanted = self.session_edit.text().strip() or None
        current = self.service.session
        if current is None or (wanted and wanted != current.session_id):
            self.service.new_session(wanted)
            self._log(f"Session: {self.service.session.root}")
            self._load_history()
        self.settings.last_session = self.service.session.session_id
        self._save_timer.start()

    def capture_now(self) -> None:
        self._ensure_session()
        self.capture_btn.setEnabled(False)

        def work():
            self.service.capture_all()

        threading.Thread(target=work, daemon=True).start()

    def start_schedule(self) -> None:
        self._ensure_session()
        self.settings.interval_minutes = self.interval.value()
        self.service.start_schedule()
        self.resume_session_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.interval.setEnabled(False)
        self.session_edit.setEnabled(False)
        self._log(f"Schedule started: every {self.interval.value():g} min")

    def toggle_pause(self) -> None:
        if self.service.paused:
            self.service.resume()
            self.pause_btn.setText("Pause")
            self._log("Resumed (capturing now)")
        else:
            self.service.pause()
            self.pause_btn.setText("Resume")
            self._log("Paused - scheduled captures suspended")

    def stop_schedule(self) -> None:
        self.service.stop_schedule()
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self.stop_btn.setEnabled(False)
        self.interval.setEnabled(True)
        self.session_edit.setEnabled(True)
        self._update_resume_button()
        self._log("Schedule stopped")

    def _on_results(self, results: list[CaptureResult]) -> None:
        self.capture_btn.setEnabled(True)
        self._update_resume_button()
        for r in results:
            if r.error:
                self._log(f"{r.camera}: FAILED - {r.error}")
            else:
                flag = "" if r.quality.ok else "  ⚠ " + ", ".join(r.quality.warnings)
                self._log(f"{r.camera}: saved {r.path.name}{flag}")
                self.tiles[r.camera].add_capture(r.path, self.live)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self._save_timer.stop()
        self._save_state()
        self.service.shutdown()
        super().closeEvent(event)
