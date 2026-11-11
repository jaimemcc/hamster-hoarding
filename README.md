# hamster-hoarding

Time-lapse still imaging from multiple USB webcams (initially 4× ELP-USBFHD01M-BL170IR),
with a GUI for live preview, lighting/focus checks and scheduled capture. Images are stored
per camera so they can be used for computer vision later.

## Layout

```
src/hamster_hoarding/
  __main__.py        entry point (launches the GUI)
  config.py          settings dataclasses + YAML load/save
  service.py         CaptureService: owns cameras, timed capture (GUI-independent)
  storage.py         on-disk session layout and capture log
  cameras/           camera backends (OpenCV, mock) and image-quality checks
  gui/               PySide6 main window
config/default.yaml  default settings (mock cameras); put real ones in config/local.yaml
tests/
TODO.md              task list
```

## Setup

Uses [pixi](https://pixi.sh) (Windows and Linux); dependencies are declared in `pyproject.toml`.

```
pixi install
pixi run app     # launch the GUI (config/local.yaml if present, else default.yaml)
pixi run test
pixi run lint
```

The default config uses mock cameras so the GUI runs without hardware. For real ones run
`pixi run detect --skip 0 --write-config` (skip the laptop's built-in webcam; snapshots go to
`data/detect/` so you can see which physical camera is which), then edit `config/local.yaml`.
Devices are indices on Windows and stable `/dev/v4l/by-path/...` paths on Linux. Exposure, gain,
rotation and metadata can be edited in the GUI; changes are saved automatically to
`config/last_used.yaml` and restored next time if "Load last saved settings on startup" is ticked.
Use "Resume last session" to keep adding to the previous session folder after a restart.

### Saving USB bandwidth
Untick "Live preview" once settings are dialled in. Cameras then stop streaming; each capture
opens, warms up, grabs and closes the cameras one at a time (about 3-4 s per camera), so only
one camera is on the USB bus at once. Tiles keep showing the last captured image, and the
◀/▶ buttons on each tile browse earlier captures of that camera while capture keeps running.
Exposure/gain can only be previewed with Live preview on.

## Data layout

```
data/<session>/
  session.json                          settings snapshot and start time
  captures.csv                          timestamp, camera, <metadata fields>, file, brightness, ...
  cam1/cam1_H01_20261110T160439.jpg     (metadata in filename is optional: filename_fields)
  cam2/...
```

Metadata (e.g. `animal_id`, `cage`) is configured per camera in the YAML via `metadata_fields`,
`filename_fields` and each camera's `metadata:`; it can also be edited in the GUI tiles.
Use **Pause** during feeding: scheduled captures stop, and **Resume** takes an image
immediately and continues on the interval.

The camera `name` in the config is the identity written into folder/file names and the CSV,
so images can always be traced to their camera regardless of USB device numbering.

## Linux notes

Add your user to the `video` group; list devices with `v4l2-ctl --list-devices`.
