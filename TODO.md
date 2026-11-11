# TODO

## Resume here (next session)
State: working GUI + capture pipeline, tested on mock cameras and 1 real ELP camera (Windows).
Pushed to `main`. 7 tests pass, lint clean. Only 1 ELP connected so far (4-camera setup untested).

Hardware findings (Windows, 1 ELP camera): it opens at DSHOW index 1 (index 0 is the laptop
webcam); 1080p MJPG works; the first ~1s after opening is overexposed, so `warmup_seconds`
(default 3) delays the first capture. Exposure/gain are controllable. Cameras REMEMBER their
last exposure mode, so the app sets auto/manual explicitly on open. Exposure units differ per
platform (DSHOW log2 seconds -13..0; V4L2 100us units): see `EXPOSURE_RANGE` in
`cameras/camera.py`. The Linux V4L2 values there are UNTESTED.
Real-camera config lives in `config/local.yaml` (git-ignored); `pixi run detect` helps make it.
GUI edits (exposure, gain, rotate, metadata, interval, last session) auto-save to
`config/last_used.yaml` (git-ignored); the "Load last saved settings on startup" checkbox
makes the next start use it. `--config` always overrides.

LED array: no software control (ELP LEDs/IR-cut follow the board's photosensor; no UVC property).
Decision: user will cover the LEDs with opaque tape (or disconnect the LED board connector) for
the whole experiment if lights-off is wanted. Don't cover the photosensor.

Open questions for the user:
- Confirm camera mounting orientation once decided (rotate is now a per-tile GUI option).

Suggested next steps, in order:
1. Plug in all 4 cameras; run `pixi run detect --skip 0 --write-config`, check the preview grid.
2. Tune the quality thresholds in `cameras/quality.py` on real images (visible + IR modes).
3. Reconnect-on-drop and per-camera health; check USB bandwidth before going to 8 cameras.
4. Add GitHub Actions CI (ruff + pytest). Then test on the Linux laptop (`pixi install`, `video` group).

## Setup
- [x] Project skeleton, pixi environment (Windows + Linux)
- [x] Publish `jaimemcc/hamster-hoarding` (public)
- [ ] CI: GitHub Actions running ruff + pytest

## Cameras
- [x] Camera abstraction with threaded capture, OpenCV + mock backends
- [x] Image-quality checks (brightness, clipping, sharpness)
- [x] Camera enumeration helper (`pixi run detect [--skip 0] [--write-config]`)
- [x] Per-camera exposure (auto/manual), gain and rotate in GUI
- [ ] Brightness/contrast/white-balance controls, resolution in GUI
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
- [x] Configurable per-camera metadata (CSV columns, optional filename inclusion); `animal_id`, `condition`
- [x] GUI edits auto-saved to config/last_used.yaml; "load last saved settings" checkbox
- [x] Resume last session button (appends to existing folder/CSV; new metadata columns are added)
- [ ] Export / analysis helpers

## Experiment
- [x] Run continuously until stopped; pause/resume (e.g. feeding)
- [x] Resume a session after a crash/restart ("Resume last session" button)

## Testing
- [x] Mock camera + tests for capture layout
- [ ] Test on Linux laptop with real cameras (V4L2, `video` group, exposure/gain controls)
- [ ] Test on real ELP cameras on Windows
