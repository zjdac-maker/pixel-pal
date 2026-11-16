"""Entry point: ``python -m pixelpal`` or the ``pixel-pal`` command."""
from __future__ import annotations

import argparse
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pixel-pal", description="Your desktop buddy with a job.")
    parser.add_argument("--version", action="version", version=f"pixel-pal {__version__}")
    parser.add_argument("--run-seconds", type=float, default=0.0,
                        help="quit automatically after this many seconds (used for smoke tests)")
    args = parser.parse_args(argv)

    from PySide6.QtCore import QLockFile, Qt, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    from .config import config_dir

    # Honour 125% / 150% display scaling exactly instead of rounding it.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("pixel-pal")
    app.setQuitOnLastWindowClosed(False)      # the pet lives in the tray; dialogs closing must not end it

    config_dir().mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(config_dir() / "pixel-pal.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        print("pixel-pal is already running.", file=sys.stderr)
        return 1

    from .app import PetController
    controller = PetController()
    controller.start()
    if args.run_seconds > 0:
        QTimer.singleShot(int(args.run_seconds * 1000), controller.quit)
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
