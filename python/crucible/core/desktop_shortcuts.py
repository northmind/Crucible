from __future__ import annotations

"""Desktop shortcut creation and cleanup for game entries."""

import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from crucible.core.paths import Paths, safe_name
from crucible.core.types import GameDict

logger = logging.getLogger(__name__)

_ICON_EXTRACT_TIMEOUT_SECS = 15
_RUN_QUIET_TIMEOUT_SECS = 10


class DesktopShortcutMixin:
    """Desktop-file management methods for GameLauncher.

    Expects the concrete class to have: ``_gm`` (GameManager reference),
    ``launcher_desktop_file``.
    """

    @staticmethod
    def _desktop_dir() -> Path:
        """Return the XDG applications directory."""
        return Path.home() / '.local/share/applications'

    @staticmethod
    def _game_desktop_path(game_name: str) -> Path:
        """Return the .desktop file path for a given game."""
        return DesktopShortcutMixin._desktop_dir() / f"crucible-{safe_name(game_name)}.desktop"

    @staticmethod
    def _game_icon_path(game_name: str, exe_path: str = '') -> Path:
        """Return the cached icon path inside the game's artwork folder."""
        import hashlib as _hl
        if exe_path:
            digest = _hl.sha1(exe_path.strip().lower().encode('utf-8')).hexdigest()[:16]
            key = f'exe_{digest}'
        else:
            key = safe_name(game_name)
        return Paths.artwork_dir() / key / 'icon.png'

    @staticmethod
    def _run_quiet(command: list[str]) -> None:
        """Run a command silently, discarding stdout and stderr."""
        try:
            subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=_RUN_QUIET_TIMEOUT_SECS,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug(f"Quiet command {command[0]} failed: {exc}")

    @staticmethod
    def _desktop_exec_arg(value: str) -> str:
        """Escape one argument for a .desktop Exec field."""
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @classmethod
    def _refresh_desktop_database(cls) -> None:
        """Invoke update-desktop-database for the applications directory."""
        cls._run_quiet(['update-desktop-database', str(cls._desktop_dir())])

    def _find_tool(self, name: str) -> str:
        """Locate a helper tool in APPDIR or on PATH."""
        appdir = os.environ.get('APPDIR', '')
        if appdir:
            candidate = Path(appdir) / 'usr' / 'bin' / name
            if candidate.exists():
                return str(candidate)
        return shutil.which(name) or ''

    def _extract_exe_icon(self, exe_path: str, icon_path: Path) -> bool:
        """Extract the highest-resolution icon from an .exe and save as PNG.

        Tries ``wrestool`` / ``icotool`` (icoutils) first — these are bundled
        inside the AppImage.  If the CLI tools are unavailable (e.g. running
        from source), falls back to a pure-Python PE parser + Pillow.
        """
        if self._extract_exe_icon_cli(exe_path, icon_path):
            return True
        return self._extract_exe_icon_python(exe_path, icon_path)

    def _extract_exe_icon_cli(self, exe_path: str, icon_path: Path) -> bool:
        """Extract icon using wrestool/icotool CLI tools (icoutils)."""
        wrestool = self._find_tool('wrestool')
        icotool = self._find_tool('icotool')
        if not wrestool or not icotool:
            return False
        import tempfile
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                ico_dir = tmp_dir / 'ico'
                png_dir = tmp_dir / 'png'
                ico_dir.mkdir()
                png_dir.mkdir()

                subprocess.run(
                    [wrestool, '-x', '--type=14', '-o', str(ico_dir), exe_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=_ICON_EXTRACT_TIMEOUT_SECS,
                )
                ico_files = sorted(ico_dir.glob('*.ico'))
                if not ico_files:
                    return False

                subprocess.run(
                    [icotool, '-x', '-o', str(png_dir)] + [str(f) for f in ico_files],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=_ICON_EXTRACT_TIMEOUT_SECS,
                )

                def _rank(p: Path) -> tuple[int, int]:
                    """Sort key: (resolution, file_size) — largest wins."""
                    m = re.search(r'_(\d+)x\d+x', p.name)
                    res = int(m.group(1)) if m else 0
                    return (res, p.stat().st_size)

                # Filter out corrupt PNGs (< 2 KB for a 16x16 is already suspicious;
                # a valid 256x256 is always well above this threshold).
                _MIN_ICON_BYTES = 2048
                pngs = [p for p in png_dir.glob('*.png') if p.stat().st_size >= _MIN_ICON_BYTES]
                pngs.sort(key=_rank, reverse=True)
                if not pngs:
                    return False

                icon_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(str(pngs[0]), str(icon_path))
                return True
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug(f"CLI icon extraction failed for {exe_path}: {exc}")
            return False

    @staticmethod
    def _extract_exe_icon_python(exe_path: str, icon_path: Path) -> bool:
        """Extract icon using pure-Python PE parser + Pillow (no external tools)."""
        from crucible.core.icon_extract import extract_icon_to_png
        return extract_icon_to_png(exe_path, icon_path)

    @staticmethod
    def _find_artwork_icon(exe_path: str, game_name: str) -> str:
        """Return the path to cached Steam artwork if it exists, else empty string.

        Checks the per-game artwork folder for header artwork.
        """
        import hashlib as _hl
        artwork_dir = Paths.artwork_dir()
        candidates: list[Path] = []
        if exe_path:
            digest = _hl.sha1(exe_path.strip().lower().encode('utf-8')).hexdigest()[:16]
            candidates.append(artwork_dir / f'exe_{digest}' / 'header.jpg')
        candidates.append(artwork_dir / safe_name(game_name) / 'header.jpg')
        for c in candidates:
            if c.exists():
                return str(c)
        return ''

    def _shortcut_exec_command(self, name: str) -> str:
        """Build the Exec= line for a game's .desktop file."""
        quoted_name = self._desktop_exec_arg(name)
        repo_root = Path(__file__).resolve().parents[3]
        appimage = os.environ.get('APPIMAGE', '')
        if appimage and Path(appimage).exists():
            return f'{self._desktop_exec_arg(appimage)} --launch {quoted_name}'

        installed = shutil.which('crucible')
        if installed:
            return f'{self._desktop_exec_arg(installed)} --launch {quoted_name}'

        package_root = repo_root / 'python'
        main_module = package_root / 'crucible' / '__main__.py'
        if main_module.exists():
            return (
                f'env PYTHONPATH={self._desktop_exec_arg(str(package_root))} '
                f'{self._desktop_exec_arg(sys.executable)} -m crucible --launch {quoted_name}'
            )

        return f'{self._desktop_exec_arg(sys.executable)} -m crucible --launch {quoted_name}'

    def create_game_shortcut(self, game: GameDict) -> tuple[bool, str]:
        """Create a .desktop shortcut for a game; returns (success, path_or_error)."""
        name = game.get('name', '')
        if not name:
            return False, "Game has no name"

        desktop_dir = self._desktop_dir()
        desktop_dir.mkdir(parents=True, exist_ok=True)
        desktop_path = self._game_desktop_path(name)

        exec_cmd = self._shortcut_exec_command(name)
        icon = ""
        exe_path = game.get('exe_path', '')
        if exe_path:
            icon_path = self._game_icon_path(name, exe_path)
            if icon_path.exists():
                icon = str(icon_path)
            elif self._extract_exe_icon(exe_path, icon_path):
                icon = str(icon_path)
        if not icon:
            # Fall back to cached Steam artwork (header image)
            icon = self._find_artwork_icon(exe_path, name)
        if not icon:
            icon = "crucible"

        sanitized_name = ''.join(c for c in name if c.isprintable() and c not in '\n\r;')
        sname = safe_name(name)
        content = (
            '[Desktop Entry]\n'
            'Type=Application\n'
            f'Name={sanitized_name}\n'
            f'Exec={exec_cmd}\n'
            f'Icon={icon}\n'
            'Categories=Game;\n'
            f'StartupWMClass=crucible-{sname}\n'
            'StartupNotify=false\n'
        )

        try:
            desktop_path.write_text(content, encoding='utf-8')
            desktop_path.chmod(0o755)
            self._refresh_desktop_database()
            return True, str(desktop_path)
        except OSError as e:
            logger.error(f"Failed to create shortcut for {name}: {e}")
            return False, str(e)

    def remove_game_shortcut(self, game_name: str, exe_path: str = '') -> bool:
        """Delete the .desktop shortcut and cached icon for a game."""
        desktop_path = self._game_desktop_path(game_name)
        try:
            if desktop_path.exists():
                desktop_path.unlink()
            if not exe_path and hasattr(self, '_gm'):
                game = self._gm.get_game(game_name)
                if game:
                    exe_path = game.get('exe_path', '')
            icon_path = self._game_icon_path(game_name, exe_path)
            if icon_path.exists():
                icon_path.unlink()
            return True
        except OSError as exc:
            logger.debug(f"Failed to remove shortcut for {game_name}: {exc}")
        return False

    def has_game_shortcut(self, game_name: str) -> bool:
        """Return True if a .desktop shortcut exists for the game."""
        return self._game_desktop_path(game_name).exists()

    def _cleanup_old_desktop_files(self) -> None:
        """Remove stale .desktop files for games no longer in the library."""
        desktop_dir = self._desktop_dir()
        keep = {self.launcher_desktop_file}
        for gf in self._gm.games_dir.glob('*.json'):
            keep.add(desktop_dir / f"crucible-{gf.stem}.desktop")
        for f in desktop_dir.glob('crucible-*.desktop'):
            if f in keep:
                continue
            try:
                f.unlink()
            except OSError as exc:
                logger.debug(f"Failed to remove stale desktop file {f}: {exc}")

    def _ensure_launcher_desktop_file(self) -> None:
        """Create/update the launcher's own .desktop file (AppImage only)."""
        appimage_path = os.environ.get('APPIMAGE', '')
        appdir = os.environ.get('APPDIR', '')
        if not appimage_path or not Path(appimage_path).exists():
            return

        icon_name = 'crucible'
        src_icon = Path(appdir) / 'crucible.png' if appdir else None
        if src_icon and src_icon.exists():
            icon_dest = Path.home() / '.local/share/icons/hicolor/256x256/apps/crucible.png'
            try:
                icon_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_icon), str(icon_dest))
                self._run_quiet([
                    'gtk-update-icon-cache', '-f', '-t',
                    str(Path.home() / '.local/share/icons/hicolor'),
                ])
            except OSError as e:
                logger.debug(f"Failed to install icon: {e}")
                icon_name = str(src_icon)

        content = (
            '[Desktop Entry]\n'
            'Name=Crucible\n'
            f'Exec="{appimage_path}"\n'
            f'Icon={icon_name}\n'
            'Type=Application\n'
            'Categories=Game;\n'
            'Comment=Wine/Proton game launcher\n'
            'StartupWMClass=crucible\n'
            'StartupNotify=true\n'
        )
        try:
            self.launcher_desktop_file.parent.mkdir(parents=True, exist_ok=True)
            self.launcher_desktop_file.write_text(content, encoding='utf-8')
            self._refresh_desktop_database()
        except OSError as e:
            logger.debug(f"Failed to write launcher desktop file: {e}")
