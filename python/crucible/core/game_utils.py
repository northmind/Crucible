from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _build_dll_overrides(custom_overrides: str = '') -> str:
    """Build WINEDLLOVERRIDES string from user-specified custom overrides."""
    _ALIASES = {'native': 'n', 'builtin': 'b', 'disabled': ''}
    _VALID_MODES = {'n,b', 'b,n', 'b', 'n', 'd', ''}

    buckets: dict = {'n,b': [], 'b,n': [], 'b': [], 'n': [], 'd': [], '': []}
    buckets[''].append('winemenubuilder')

    if custom_overrides:
        if '=' in custom_overrides:
            for part in custom_overrides.split(';'):
                part = part.strip()
                if not part:
                    continue
                if '=' in part:
                    dll, _, mode = part.partition('=')
                    dll = dll.strip()
                    mode = _ALIASES.get(mode.strip().lower(), mode.strip().lower())
                    if not dll:
                        continue
                    if mode not in _VALID_MODES:
                        logger.warning(f"Unknown DLL override mode '{mode}' for '{dll}', using n,b")
                        mode = 'n,b'
                    buckets[mode].append(dll)
                else:
                    dll = part.strip()
                    if dll:
                        buckets['n,b'].append(dll)
        else:
            for dll in custom_overrides.split(','):
                dll = dll.strip()
                if dll:
                    buckets['n,b'].append(dll)

    parts = []
    for mode, dlls in buckets.items():
        if dlls:
            parts.append(f"{','.join(sorted(dlls))}={mode}")
    return ';'.join(parts)


def _load_json_file(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json_file(path: Path, data: dict[str, Any]) -> None:
    """Atomically write JSON data to a file using a temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix='.tmp', dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
        os.replace(tmp_path, path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise
