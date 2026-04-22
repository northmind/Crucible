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


def _instance_server_name() -> str:
    import os

    user_id = getattr(os, "getuid", lambda: os.environ.get("USER", "unknown"))()
    return f"crucible-gui-{user_id}"


def _notify_existing_instance(server_name: str) -> bool:
    from PyQt6.QtCore import QIODevice
    from PyQt6.QtNetwork import QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(server_name, QIODevice.OpenModeFlag.WriteOnly)
    if not socket.waitForConnected(250):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(250)
    socket.disconnectFromServer()
    return True


def _install_instance_server(server_name: str, window):
    from PyQt6.QtNetwork import QLocalServer

    server = QLocalServer()

    def _restore_existing_window() -> None:
        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            if socket is not None:
                socket.disconnectFromServer()
                socket.deleteLater()
        window.restore_and_activate()

    server.newConnection.connect(_restore_existing_window)
    if server.listen(server_name):
        return server
    QLocalServer.removeServer(server_name)
    if server.listen(server_name):
        return server
    raise RuntimeError(f"Failed to listen on single-instance server {server_name}")


def _gui() -> int:
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
    server_name = _instance_server_name()
    if _notify_existing_instance(server_name):
        return 0
    apply_log_level(log_level())
    window = MainWindow()
    app._single_instance_server = _install_instance_server(server_name, window)  # type: ignore[attr-defined]
    return app.exec()


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
    sys.exit(_gui())


if __name__ == "__main__":
    main()
