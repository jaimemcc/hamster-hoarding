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

## Quickstart: four cameras on Ubuntu

### First-time camera setup

1. Connect all four cameras. Label each camera and its USB port (and hub port, if used).
   Always reconnect each camera to the same port: Linux device paths identify ports, not cameras.
2. Open a terminal in this project folder and install dependencies if you haven't already:

   ```bash
   cd ~/Github/hamster-hoarding
   pixi install
   ```

   If the project is elsewhere, use its actual folder instead. Install [pixi](https://pixi.sh)
   first if the `pixi` command is unavailable.
3. Close the GUI and other camera apps, then detect cameras and create the local configuration:

   ```bash
   pixi run detect --write-config
   ```

   **Warning:** this overwrites `config/local.yaml` if it already exists, including camera
   names and settings. Back it up first if you need to keep them. The default configuration uses
   mock cameras; the generated local configuration selects real cameras.
4. Check the terminal output: you should see four camera entries. Open the snapshots:

   ```bash
   xdg-open data/detect
   ```

   Match each current terminal entry to its snapshot and physical camera. Old snapshots may
   remain in the folder, so use the filenames printed by the current run. If a built-in webcam
   also appears, rerun detection with its exact printed device path excluded, for example:

   ```bash
   pixi run detect --write-config --skip '/dev/v4l/by-path/REPLACE-WITH-DEVICE-PATH'
   ```

   Use the actual path from the output, not the example. Confirm the new output and snapshots
   again; camera numbers can change.
5. Edit the configuration:

   ```bash
   nano config/local.yaml
   ```

   Under `cameras:`, use the snapshots to assign each entry a unique, meaningful `name`, and
   keep its detected `device` path unchanged. The name determines the image folder and filenames,
   so record which physical camera and cage it represents and keep that mapping consistent.
   If you need per-camera metadata in the GUI and CSV, set the existing top-level
   `metadata_fields`, for example `metadata_fields: [animal_id, condition]`; optionally set
   `filename_fields: [animal_id]` to include that value in filenames. Save in nano with
   **Ctrl+O**, **Enter**, then **Ctrl+X**.
6. Launch using the new configuration explicitly:

   ```bash
   pixi run app --config config/local.yaml
   ```

   Check **Live preview**, verify all four views match their names, and adjust rotation,
   exposure, gain and metadata as needed. Tick **Load last saved settings on startup** to
   restore GUI changes next time.

### Start a recording session

1. Use **Choose folder...** to select the parent data folder; enter a session name and capture
   interval in minutes. Enter any per-camera metadata.
2. Click **Capture now** and check the log for four successful saves. Inspect the images in the
   session's camera folders before starting the experiment.
3. Click **Start schedule**. Use **Pause** during interruptions, **Resume** to continue, and
   **Stop schedule** when finished. Keep the laptop powered and prevent it from suspending.
4. If USB bandwidth causes trouble, untick **Live preview**: captures open cameras one at a
   time. Use **Capture now** and check the log to confirm all four still save successfully.

### Later sessions and troubleshooting

- Reconnect cameras to their labelled ports and run `pixi run app` from the project folder.
  GUI changes are restored if **Load last saved settings on startup** was ticked. To reload
  the local file instead, use `pixi run app --config config/local.yaml`.
- Use **Resume last session** to continue a previous session, or enter a new session name.
  Check all views and take a test capture before starting a schedule.
- If a camera is missing, close the GUI, check its cable and port, then run `pixi run detect`
  without `--write-config` to inspect devices without replacing your configuration. Compare
  the printed paths and snapshots with `config/local.yaml`; do not rely on camera numbers alone.
  If a camera moved ports, update its `device` path while keeping its `name` with the physical
  camera. Reload the local file explicitly to bypass any older saved GUI settings.
- If access is denied, check that your user has permission to access the relevant `/dev/video*`
  device. Ubuntu may grant this through a desktop-session ACL; the `video` group is another
  possible setup. Close other programs using the camera before retrying.

Use **Choose folder...** to select or create the parent data folder before a capture or schedule.
Each session still has its own subfolder there, using the session name (or a generated name).
Changing the parent folder does not move previous data and clears the last-session selection;
to continue an existing session there, enter its folder name as the session name. The folder
cannot be changed during a schedule (including while paused) or a capture. The choice is saved
with the other GUI settings and restored on startup if the load-last-settings option is enabled.

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
  notes.csv                             timestamp, kind (note/event), note
  cam1/cam1_H01_20261110T160439.jpg     (metadata in filename is optional: filename_fields)
  cam2/...
```

Metadata (e.g. `animal_id`, `cage`) is configured per camera in the YAML via `metadata_fields`,
`filename_fields` and each camera's `metadata:`; it can also be edited in the GUI tiles.
Use **Pause** during feeding: scheduled captures stop, and **Resume** takes an image
immediately and continues on the interval.

Type free-text notes (e.g. "added food", "cage disturbed") in the note box and press Enter; they
go to `notes.csv` with the same ISO timestamp format as `captures.csv`, so the two can be joined
by time. Schedule start/pause/resume/stop are logged there automatically as `event` rows.

The camera `name` in the config is the identity written into folder/file names and the CSV,
so images can always be traced to their camera regardless of USB device numbering.

On Linux, `v4l2-ctl --list-devices` can help list devices if `v4l2-ctl` is installed.
