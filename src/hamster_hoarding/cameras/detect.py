"""List connected cameras, save a snapshot of each, and optionally write a config.

    pixi run detect                      # list + save snapshots to data/detect/
    pixi run detect --write-config       # also write config/local.yaml (cam1, cam2, ...)
    pixi run detect --skip 0             # ignore a device (e.g. the laptop's built-in webcam)
"""

import argparse
import sys
import time
from pathlib import Path

import cv2

from hamster_hoarding.cameras.camera import BACKEND
from hamster_hoarding.config import DEFAULT_CONFIG, CameraSettings, Settings, save_settings

MAX_INDEX = 16
SNAPSHOT_DIR = Path("data") / "detect"


def candidate_devices() -> list[int | str]:
    """Linux: stable by-path names (tied to the USB port). Elsewhere: integer indices."""
    if sys.platform.startswith("linux"):
        by_path = Path("/dev/v4l/by-path")
        if by_path.exists():
            return sorted(str(p) for p in by_path.glob("*video-index0"))
    return list(range(MAX_INDEX))


def probe(device: int | str, width: int = 1920, height: int = 1080):
    cap = cv2.VideoCapture(device, BACKEND)
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    image = None
    deadline = time.time() + 3  # let auto-exposure settle
    while time.time() < deadline:
        ok, frame = cap.read()
        if ok:
            image = frame
    cap.release()
    return image


def main() -> int:
    parser = argparse.ArgumentParser(prog="detect")
    parser.add_argument("--skip", nargs="*", default=[], help="devices to ignore")
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_CONFIG.with_name("local.yaml"))
    args = parser.parse_args()
    skip = {str(s) for s in args.skip}

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    found = []
    for device in candidate_devices():
        if str(device) in skip:
            continue
        image = probe(device)
        if image is None:
            continue
        h, w = image.shape[:2]
        n = len(found) + 1
        snap = SNAPSHOT_DIR / f"cam{n}_device-{str(device).replace('/', '_')}.jpg"
        cv2.imwrite(str(snap), cv2.resize(image, (640, int(640 * h / w))))
        print(f"cam{n}: device={device!r} {w}x{h} snapshot={snap}")
        found.append(CameraSettings(name=f"cam{n}", device=device, width=w, height=h))

    if not found:
        print("No cameras found.")
        return 1
    print("Open the snapshots to see which physical camera is which; rename in the config.")
    if args.write_config:
        save_settings(Settings(cameras=found), args.output)
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
