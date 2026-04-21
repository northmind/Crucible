import sys
from crucible.core.logger import setup_logging
from crucible.core.runner_bootstrap import ensure_seeded_runner


def _launch_game(game_name: str) -> int:
    import time
    from crucible.core.managers import GameManager
    gm = GameManager()
    gm.scan_games()
    error = gm.launch_game(game_name)
    if error:
        print(f"crucible: {error}", file=sys.stderr)
        return 1
    while gm.is_game_running(game_name):
        time.sleep(2)
    gm.on_game_exited(game_name)
    return 0


def _gui():
    import os
    from PyQt6.QtWidgets import QApplication
    from crucible.core.logger import apply_log_level
    from crucible.ui.main_window import MainWindow
    from crucible.ui.app_settings import log_level

    # Fallback for environments without GPU / EGL
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu-compositing --disable-gpu",
    )
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

    app = QApplication(sys.argv)
    app.setApplicationName("crucible")
    apply_log_level(log_level())
    window = MainWindow()
    sys.exit(app.exec())


def main() -> None:
    logger = setup_logging()
    ensure_seeded_runner()
    if "--launch" in sys.argv:
        idx = sys.argv.index("--launch")
        if idx + 1 >= len(sys.argv):
            print("crucible: --launch requires a game name", file=sys.stderr)
            sys.exit(1)
        game_name = sys.argv[idx + 1]
        logger.info(f"Launching game: {game_name}")
        sys.exit(_launch_game(game_name))
    logger.info("Crucible Launcher starting...")
    _gui()


if __name__ == "__main__":
    main()
