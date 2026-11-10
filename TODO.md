# TODO

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
- [x] Capture now, start/stop schedule, interval, session name
- [ ] Settings panel editing cameras / output dir; save/load profiles
- [ ] Countdown to next capture, disk-space warning, image count
- [ ] Open last captured image / session folder
- [ ] IR / night lighting handling (cameras are IR-capable) - needs input

## Data
- [x] Session folder per camera, timestamped filenames, captures.csv, session.json
- [ ] Decide metadata needed for later CV (animal/cage ID per camera, notes)
- [ ] Export / analysis helpers

## Experiment
- [ ] Confirm scheduling needs (fixed duration, start/stop times, light/dark cycle)
- [ ] Resume a session after a crash/restart

## Testing
- [x] Mock camera + tests for capture layout
- [ ] Test on Linux laptop with real cameras (V4L2, `video` group, exposure/gain controls)
- [ ] Test on real ELP cameras on Windows
