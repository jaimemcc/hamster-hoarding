import argparse
import sys
from pathlib import Path

from hamster_hoarding.config import DEFAULT_CONFIG, load_settings, resolve_startup_settings

LOCAL_CONFIG = DEFAULT_CONFIG.with_name("local.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(prog="hamster-hoarding")
    parser.add_argument("--config", type=Path, help="settings YAML; overrides the last saved "
                        "settings (default: config/local.yaml, else config/default.yaml)")
    args = parser.parse_args()
    if args.config:
        settings = load_settings(args.config)
    else:
        settings, _ = resolve_startup_settings(
            LOCAL_CONFIG if LOCAL_CONFIG.exists() else DEFAULT_CONFIG
        )

    from PySide6.QtWidgets import QApplication

    from hamster_hoarding.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
