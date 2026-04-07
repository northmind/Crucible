import sys

from crucible.core.logger import setup_logging


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
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QPushButton
    from crucible.ui.main_window import MainWindow
    from crucible.ui import styles

    _orig = QPushButton.__init__
    def _init(self, *args, **kwargs):
        _orig(self, *args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    QPushButton.__init__ = _init

    app = QApplication(sys.argv)
    app.setApplicationName("crucible")
    app.setStyle("Fusion")
    app.setStyleSheet(styles.tooltip())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def main() -> None:
    """Entry point: parse CLI args and either launch a game or start the GUI."""
    logger = setup_logging()

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
