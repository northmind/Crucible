from __future__ import annotations

"""Environment and command-line assembly for game launches."""

import logging
import os
import resource
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from crucible.core.paths import Paths, safe_name
from crucible.core.types import GameDict, GamescopeSettings

if TYPE_CHECKING:
    from crucible.core.managers import GameManager

logger = logging.getLogger(__name__)

_MIN_NOFILE_LIMIT = 524288


def validate_launch_prereqs(game: GameDict, gm: GameManager) -> str:
    """Return an error string if the game cannot be launched, else ''."""
    exe_path = game['exe_path']
    proton_version = game.get('proton_version', '')
    proton_path = (
        (gm.find_proton_path(proton_version) if proton_version else '')
        or game.get('proton_path', '')
    )
    if not Path(exe_path).exists():
        return f"Executable not found:\n{exe_path}"
    if not proton_path or not Path(proton_path).is_dir():
        return "No Proton version configured.\nEdit the game and select a Proton version."
    umu = gm.find_umu_run()
    if not umu:
        return "umu-run not found.\nCheck that it is installed or bundled with the AppImage."
    return check_nofile_limit(game)


def check_nofile_limit(game: GameDict) -> str:
    """Return an error if the file descriptor limit is too low for esync/fsync."""
    env_vars = game.get('env_vars', {})
    if env_vars.get('PROTON_NO_ESYNC') == '1' or env_vars.get('PROTON_NO_FSYNC') == '1':
        return ''
    try:
        _, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if hard != resource.RLIM_INFINITY and hard < _MIN_NOFILE_LIMIT:
            return (
                f"ESYNC/FSYNC require an open file descriptor limit of at least 524288.\n"
                f"Current hard limit is {hard}.\n\n"
                f"Add to /etc/systemd/user.conf or /etc/security/limits.conf:\n"
                f"  DefaultLimitNOFILE=1048576\n\n"
                f"Or disable ESYNC/FSYNC in the advanced tab."
            )
    except (OSError, ValueError) as exc:
        logger.debug(f"Could not evaluate RLIMIT_NOFILE: {exc}")
    return ''


def resolve_prefix(game: GameDict, sname: str, prefixes_dir: Path) -> Path:
    """Ensure the Wine prefix directory exists and return its path."""
    stored_prefix = game.get('prefix_path', '').strip()
    prefix_path = Path(stored_prefix) if stored_prefix else prefixes_dir / f"{sname}prefix"
    prefix_path.mkdir(parents=True, exist_ok=True)
    return prefix_path


# Minimum expected entries in a healthy Wine/Proton prefix.
_PREFIX_REQUIRED_ENTRIES: tuple[str, ...] = (
    "dosdevices",
    "drive_c",
    "system.reg",
    "user.reg",
    "userdef.reg",
)


def validate_prefix(prefix_path: Path) -> str:
    """Return a warning string if the prefix looks corrupted, else ``""``.

    A brand-new (empty) prefix is fine — Proton will populate it on first
    run.  But a prefix that has *some* files yet is missing core entries
    is likely corrupted and will cause a silent failure at launch time.
    """
    if not any(prefix_path.iterdir()):
        return ""  # fresh prefix — Proton will initialise it

    missing = [e for e in _PREFIX_REQUIRED_ENTRIES if not (prefix_path / e).exists()]
    if not missing:
        return ""

    names = ", ".join(missing)
    return (
        f"Wine prefix appears corrupted — missing: {names}\n"
        f"Path: {prefix_path}\n\n"
        f"You can reset the prefix from the game's settings,\n"
        f"or delete it manually and let Proton recreate it."
    )


_SCRIPT_TIMEOUT_SECS = 30


def run_launch_script(script_path: str, *, label: str = "script") -> str:
    """Run a user-provided launch script.  Returns error string or ``""``.

    The script must be an executable file.  It runs with a timeout and
    inherits the current environment.  Non-zero exit is treated as a
    blocking error for pre-launch scripts but only logged for post-launch.
    """
    if not script_path or not script_path.strip():
        return ""
    path = Path(script_path.strip())
    if not path.is_file():
        return f"{label} not found: {path}"
    if not os.access(str(path), os.X_OK):
        return f"{label} is not executable: {path}"
    try:
        result = subprocess.run(
            [str(path)], timeout=_SCRIPT_TIMEOUT_SECS,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()[:200]
            return f"{label} exited with code {result.returncode}" + (
                f": {stderr}" if stderr else ""
            )
    except subprocess.TimeoutExpired:
        return f"{label} timed out after {_SCRIPT_TIMEOUT_SECS}s"
    except OSError as exc:
        return f"Failed to run {label}: {exc}"
    return ""


def prepare_log_dir(game_name: str, timestamp_log_path: Callable[[Path], Path]) -> Path:
    """Clear old logs and return a fresh log file path."""
    log_dir = Paths.game_logs_dir(game_name)
    for old_log in log_dir.glob("*.log"):
        try:
            old_log.unlink()
        except OSError as exc:
            logger.debug(f"Failed to remove old log {old_log}: {exc}")
    return timestamp_log_path(log_dir)


def build_env(game: GameDict, game_name: str, sname: str,
              proton_path: str, prefix_path: Path,
              resolve_appid: Callable[[GameDict], str],
              steam_id_for_name: Callable[[str, str], str],
              build_dll_overrides: Callable[[str], str]) -> dict[str, str]:
    """Assemble the environment dict for the game process."""
    from crucible.core.paths import strip_launch_env

    env = {k: v for k, v in os.environ.items() if not k.startswith('BASH_FUNC')}
    strip_launch_env(env)
    env.update(game.get('env_vars', {}))
    env = {k: str(v) for k, v in env.items() if k and v is not None}

    raw_appid = resolve_appid(game)
    steam_id = steam_id_for_name(game_name, raw_appid)
    env['GAMEID'] = steam_id
    env['SteamAppId'] = steam_id
    env['SteamGameId'] = steam_id

    if env.get('PROTON_LOG') == '1':
        log_dir = Paths.game_logs_dir(game_name)
        env['UMU_LOG'] = '1'
        env['PROTON_LOG_DIR'] = str(log_dir)
    else:
        env.pop('UMU_LOG', None)
        env.pop('PROTON_LOG_DIR', None)
    env['WINEPREFIX'] = str(prefix_path)
    env['PROTONPATH'] = proton_path
    env['WINEARCH'] = 'win64'
    env['PROTON_VERB'] = 'waitforexitandrun'

    if 'LC_ALL' in env and 'HOST_LC_ALL' not in env:
        env['HOST_LC_ALL'] = env['LC_ALL']

    env['WINEDLLOVERRIDES'] = build_dll_overrides(game.get('custom_overrides', ''))

    if 'WINEDEBUG' not in env:
        env['WINEDEBUG'] = '' if env.get('PROTON_LOG') == '1' else '-all'
    if 'DXVK_LOG_LEVEL' not in env:
        env['DXVK_LOG_LEVEL'] = 'info' if env.get('PROTON_LOG') == '1' else 'error'

    if 'PULSE_LATENCY_MSEC' not in env:
        env['PULSE_LATENCY_MSEC'] = '60'

    env.setdefault('__GL_SHADER_DISK_CACHE', '1')
    shader_cache_dir = Paths.data_dir() / 'shader_cache' / sname
    shader_cache_dir.mkdir(parents=True, exist_ok=True)
    env.setdefault('__GL_SHADER_DISK_CACHE_PATH', str(shader_cache_dir))

    if env.get('PROTON_ENABLE_NVAPI') == '1':
        env.setdefault('DXVK_ENABLE_NVAPI', '1')
        env.setdefault('DXVK_NVAPI_ALLOW_OTHER_DRIVERS', '1')

    env['CRUCIBLE_GAME_ID'] = str(uuid.uuid4())
    return env


def _detect_gamescope_version(gamescope_bin: str) -> bool:
    """Return True if gamescope is "new" style (>= 3.12, has -F/--filter flag)."""
    try:
        result = subprocess.run(
            [gamescope_bin, "--help"],
            capture_output=True, text=True, timeout=5,
        )
        return "-F, --filter" in (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return False


def build_gamescope_command(settings: GamescopeSettings) -> list[str]:
    """Convert structured gamescope settings into a CLI prefix list.

    Returns an empty list if gamescope is disabled or not installed.
    The returned list ends with ``--`` so the caller can append the game
    command directly.

    Flag mapping matches Heroic Games Launcher (v2.x):
      -w/-h   game render resolution
      -W/-H   gamescope output resolution
      -F fsr/-U   upscale method (new/old)
      -f/-b       window type
      -r/-o       FPS limiter
      --force-grab-cursor
    """
    has_upscale = settings.get("enable_upscaling", False)
    has_limiter = settings.get("enable_limiter", False)
    if not has_upscale and not has_limiter:
        return []

    gamescope_bin = shutil.which("gamescope")
    if not gamescope_bin:
        logger.warning("Gamescope enabled but 'gamescope' not found on PATH.")
        return []

    new_version = _detect_gamescope_version(gamescope_bin)
    cmd: list[str] = [gamescope_bin]

    if has_upscale:
        gw = settings.get("game_width", "")
        gh = settings.get("game_height", "")
        uw = settings.get("upscale_width", "")
        uh = settings.get("upscale_height", "")
        if gw:
            cmd += ["-w", gw]
        if gh:
            cmd += ["-h", gh]
        if uw:
            cmd += ["-W", uw]
        if uh:
            cmd += ["-H", uh]

        method = settings.get("upscale_method", "")
        if method == "fsr":
            cmd += ["-F", "fsr"] if new_version else ["-U"]
        elif method == "nis":
            cmd += ["-F", "nis"] if new_version else ["-Y"]
        elif method == "integer":
            cmd += ["-S", "integer"] if new_version else ["-i"]
        elif method == "stretch" and new_version:
            cmd += ["-S", "stretch"]

        wt = settings.get("window_type", "")
        if wt == "fullscreen":
            cmd.append("-f")
        elif wt == "borderless":
            cmd.append("-b")

    if has_limiter:
        fps = settings.get("fps_limiter", "")
        fps_nf = settings.get("fps_limiter_no_focus", "")
        if fps:
            cmd += ["-r", fps]
        if fps_nf:
            cmd += ["-o", fps_nf]

    if settings.get("enable_force_grab_cursor", False):
        cmd.append("--force-grab-cursor")

    extra = settings.get("additional_options", "").strip()
    if extra:
        try:
            cmd += shlex.split(extra)
        except ValueError as exc:
            logger.warning("Could not parse gamescope additional_options: %s", exc)

    cmd.append("--")
    return cmd


def build_command(game: GameDict, umu: str, exe_path: str,
                  game_name: str, game_uuid: str, gm: GameManager) -> list[str]:
    """Assemble the final command line for the game."""
    raw_args = game.get('launch_args', '').strip()
    try:
        cmd_args = shlex.split(raw_args) if raw_args else []
    except ValueError as e:
        logger.warning(f"Could not parse launch_args '{raw_args}': {e}")
        cmd_args = []

    game_cmd = [umu, exe_path] + cmd_args

    if game.get('fingerprint_lock'):
        bwrap_args = gm.fingerprint.get_bwrap_args(game_name)
        if bwrap_args:
            game_cmd = bwrap_args + game_cmd

    wrapper_str = (game.get('wrapper_command') or '').strip()
    if wrapper_str:
        try:
            game_cmd = shlex.split(wrapper_str) + game_cmd
        except ValueError as e:
            logger.warning(f"Could not parse wrapper command '{wrapper_str}': {e}")

    if game.get('enable_gamemode') and shutil.which('gamemoderun'):
        game_cmd = ['gamemoderun'] + game_cmd

    if shutil.which('systemd-run'):
        game_cmd = [
            'systemd-run', '--user', '--scope',
            f'--unit=game-{safe_name(game_name)}-{game_uuid[:8]}',
            '--',
        ] + game_cmd

    # Gamescope wraps everything — must be outermost.
    if game.get('enable_gamescope'):
        gs_settings = game.get('gamescope_settings') or {}
        gs_cmd = build_gamescope_command(gs_settings)
        if gs_cmd:
            game_cmd = gs_cmd + game_cmd

    return game_cmd
