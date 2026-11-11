import threading

import cv2
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
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
from hamster_hoarding.config import CameraSettings, Settings
from hamster_hoarding.service import CaptureResult, CaptureService

PREVIEW_SIZE = (480, 270)


class CameraTile(QGroupBox):
    def __init__(self, cam: CameraSettings, fields: list[str], on_controls_changed):
        super().__init__(cam.name)
        self.cam = cam
        self._on_controls_changed = on_controls_changed
        self.image = QLabel("no signal")
        self.image.setFixedSize(*PREVIEW_SIZE)
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setStyleSheet("background: #222; color: #aaa;")
        self.info = QLabel(" ")
        layout = QVBoxLayout(self)
        layout.addWidget(self.image)
        layout.addWidget(self.info)

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
        self.auto_exp.toggled.connect(self._controls_changed)
        self.exposure.valueChanged.connect(self._controls_changed)
        self.gain.valueChanged.connect(self._controls_changed)
        row = QHBoxLayout()
        row.addWidget(self.auto_exp)
        row.addWidget(QLabel("Exposure"))
        row.addWidget(self.exposure)
        row.addWidget(QLabel("Gain"))
        row.addWidget(self.gain)
        layout.addLayout(row)

        form = QFormLayout()
        for key in fields:
            edit = QLineEdit(cam.metadata.get(key, ""))
            edit.textChanged.connect(lambda text, k=key: self.cam.metadata.__setitem__(k, text))
            form.addRow(key, edit)
        layout.addLayout(form)

    def _controls_changed(self) -> None:
        auto = self.auto_exp.isChecked()
        self.exposure.setEnabled(not auto)
        self.cam.exposure = None if auto else float(self.exposure.value())
        self.cam.gain = float(self.gain.value())
        self._on_controls_changed(self.cam.name)

    def show_frame(self, bgr) -> None:
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
        self.image.setText(message)


class _Bridge(QObject):
    """Moves results from worker threads onto the GUI thread."""

    results = Signal(list)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.service = CaptureService(settings)
        self.setWindowTitle("Hamster Hoarding")

        self.bridge = _Bridge()
        self.bridge.results.connect(self._on_results)
        self.service.on_results = self.bridge.results.emit

        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        grid = QGridLayout()
        self.tiles: dict[str, CameraTile] = {}
        for i, cam in enumerate(settings.cameras):
            tile = CameraTile(cam, settings.metadata_fields, self._apply_controls)
            self.tiles[cam.name] = tile
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
        self.start_btn = QPushButton("Start schedule")
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        self.stop_btn = QPushButton("Stop schedule")
        self.stop_btn.setEnabled(False)
        controls.addWidget(QLabel("Session:"))
        controls.addWidget(self.session_edit)
        controls.addWidget(QLabel("Interval:"))
        controls.addWidget(self.interval)
        controls.addWidget(self.capture_btn)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.stop_btn)
        root.addLayout(controls)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        root.addWidget(self.log)

        self.capture_btn.clicked.connect(self.capture_now)
        self.start_btn.clicked.connect(self.start_schedule)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.stop_btn.clicked.connect(self.stop_schedule)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_previews)
        self.timer.start(200)

        for name, err in self.service.open_cameras().items():
            self._log(f"{name}: {err}")
            self.tiles[name].show_error(err)

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _apply_controls(self, name: str) -> None:
        cam = self.service.cameras.get(name)
        if cam is not None:
            cam.apply_controls()

    def _refresh_previews(self) -> None:
        for name, cam in self.service.cameras.items():
            frame = cam.latest()
            if frame is not None:
                self.tiles[name].show_frame(frame.image)

    def _ensure_session(self) -> None:
        # A session is fixed once created; changing the name starts a new one.
        wanted = self.session_edit.text().strip() or None
        current = self.service.session
        if current is None or (wanted and wanted != current.session_id):
            self.settings.interval_minutes = self.interval.value()
            self.service.new_session(wanted)
            self._log(f"Session: {self.service.session.root}")

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
        self._log("Schedule stopped")

    def _on_results(self, results: list[CaptureResult]) -> None:
        self.capture_btn.setEnabled(True)
        for r in results:
            if r.error:
                self._log(f"{r.camera}: FAILED - {r.error}")
            else:
                flag = "" if r.quality.ok else "  ⚠ " + ", ".join(r.quality.warnings)
                self._log(f"{r.camera}: saved {r.path.name}{flag}")

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self.service.close_cameras()
        super().closeEvent(event)
