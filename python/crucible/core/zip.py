from __future__ import annotations

import zipfile
from pathlib import Path
from typing import NamedTuple

from crucible.core.paths import ensure_within_dir

_MAX_TOTAL_EXTRACT_SIZE = 20 * 1024 * 1024 * 1024  # 20 GB
_MAX_FILE_COUNT = 50_000


class ExtractedZipContents(NamedTuple):
    dlls: list[str]
    exes: list[str]


def _validate_zip_members(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    base_dir = dest_dir.resolve()
    total_size = 0
    file_count = 0
    for info in zf.infolist():
        name = info.filename
        if not name:
            continue
        member_path = Path(name)
        if member_path.is_absolute():
            raise ValueError(f"Archive member has absolute path: {name}")
        ensure_within_dir(base_dir, (base_dir / member_path).resolve())
        total_size += info.file_size
        file_count += 1
    if total_size > _MAX_TOTAL_EXTRACT_SIZE:
        raise ValueError(
            f"Archive uncompressed size ({total_size} bytes) exceeds limit of {_MAX_TOTAL_EXTRACT_SIZE} bytes"
        )
    if file_count > _MAX_FILE_COUNT:
        raise ValueError(
            f"Archive contains {file_count} entries, exceeds limit of {_MAX_FILE_COUNT}"
        )


def extract(zip_path: str, dest_dir: str) -> ExtractedZipContents:
    """Extract a ZIP archive to dest_dir and return its DLL and EXE contents.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Directory to extract into (created if it doesn't exist).

    Returns:
        ExtractedZipContents with sorted lists of DLL stems and EXE absolute paths.

    Raises:
        ValueError: If the archive contains path-traversal members, exceeds
            the 20 GB size limit, or exceeds the 50 000 file count limit.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        _validate_zip_members(zf, dest)
        zf.extractall(dest)
        names = zf.namelist()

    dlls = sorted({Path(name).stem for name in names if name.lower().endswith('.dll')})
    exes = sorted(
        {
            str((dest / Path(name)).resolve())
            for name in names
            if name.lower().endswith('.exe')
        },
        key=lambda path: (len(Path(path).parts), path.lower()),
    )
    return ExtractedZipContents(dlls=dlls, exes=exes)
