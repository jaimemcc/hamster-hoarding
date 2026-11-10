# TODO

## Resume here (next session)
State: working GUI + capture pipeline on mock cameras, pushed to `main`. 4 tests pass, lint clean.
Not yet tried with real ELP-USBFHD01M-BL170IR cameras.

Open questions for the user:
- Which per-camera metadata fields are wanted (placeholders: `animal_id`, `cage`)?
- Save GUI-edited metadata back to `config/local.yaml` so it survives restarts?
- Add a "resume last session" button, or is typing the session name fine?

Suggested next steps, in order:
1. Camera enumeration helper: list connected devices and generate `config/local.yaml`
   (Windows indices; Linux `/dev/v4l/by-path/...`).
2. Plug in the real cameras; verify 1080p MJPG capture and the 4-camera preview.
3. Tune the quality thresholds in `cameras/quality.py` on real images (visible + IR modes).
4. Per-camera exposure/gain/brightness controls in the GUI (V4L2 vs DirectShow differ).
5. Persist metadata/settings from the GUI; resume-session button.
6. Reconnect-on-drop and per-camera health; check USB bandwidth before going to 8 cameras.
7. Add GitHub Actions CI (ruff + pytest). Then test on the Linux laptop (`pixi install`, `video` group).

## Setup
- [x] Project skeleton, pixi environment (Windows + Linux)
- [x] Publish `jaimemcc/hamster-hoarding` (public)
- [ ] CI: GitHub Actions running ruff + pytest

## Cameras
- [x] Camera abstraction with threaded capture, OpenCV + mock backends
- [x] Image-quality checks (brightness, clipping, sharpness)
- [ ] Camera enumeration helper (list devices; generate config incl. Linux by-path names)
- [ ] Per-camera settings in GUI: exposure, gain, brightness, resolution (V4L2 vs DirectShow differ)
- [ ] Reconnect on camera drop/USB glitch; show per-camera health
- [ ] Up to 8 cameras: check USB bandwidth (MJPG, separate controllers/hubs), GUI tile layout
- [ ] Optional focus/white-balance lock so images are consistent over days

## GUI
- [x] Live preview grid with per-camera quality indicator
- [x] Capture now, start/pause/resume/stop schedule (runs until stopped), interval, session name
- [x] Per-camera metadata fields editable in GUI
- [ ] Settings panel editing cameras / output dir; save/load profiles
- [ ] Countdown to next capture, disk-space warning, image count
- [ ] Open last captured image / session folder
- [ ] IR / night lighting handling (cameras are IR-capable) - needs input

## Data
- [x] Session folder per camera, timestamped filenames, captures.csv, session.json
- [x] Configurable per-camera metadata (CSV columns, optional filename inclusion)
- [ ] Persist GUI-edited metadata back to config/local.yaml (currently only recorded in the CSV)
- [ ] Decide metadata needed for later CV (animal/cage ID per camera, notes)
- [ ] Export / analysis helpers

## Experiment
- [x] Run continuously until stopped; pause/resume (e.g. feeding)
- [ ] Resume a session after a crash/restart (storage already appends to an existing session)

## Testing
- [x] Mock camera + tests for capture layout
- [ ] Test on Linux laptop with real cameras (V4L2, `video` group, exposure/gain controls)
- [ ] Test on real ELP cameras on Windows
