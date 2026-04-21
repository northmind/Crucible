from __future__ import annotations

import tarfile
from pathlib import Path

from crucible.core.paths import ensure_within_dir


def validate_tar_members(tar: tarfile.TarFile, dest_dir: Path) -> None:
    """Reject archive members that escape *dest_dir* via traversal or symlinks."""
    base_dir = dest_dir.resolve()
    for member in tar.getmembers():
        member_path = Path(member.name)
        if member_path.is_absolute():
            raise ValueError(f"Archive member has absolute path: {member.name}")

        resolved_member = (base_dir / member_path).resolve()
        ensure_within_dir(base_dir, resolved_member)

        if member.issym():
            link_target = Path(member.linkname)
            if link_target.is_absolute():
                raise ValueError(f"Archive symlink has absolute target: {member.linkname}")
            ensure_within_dir(base_dir, (resolved_member.parent / link_target).resolve())
        elif member.islnk():
            link_target = Path(member.linkname)
            if link_target.is_absolute():
                raise ValueError(f"Archive hard link has absolute target: {member.linkname}")
            ensure_within_dir(base_dir, (base_dir / link_target).resolve())


def extract_tarball(tar_path: str | Path, dest_dir: str | Path) -> Path:
    """Extract a tarball safely and return the root directory of its contents.

    If the archive contains a single top-level directory, that directory is
    returned.  Otherwise *dest_dir* itself is returned.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tar_path, 'r:*') as tar:
        validate_tar_members(tar, dest_dir)
        tar.extractall(dest_dir, filter='data')

    extracted_items = list(dest_dir.iterdir())
    if len(extracted_items) == 1 and extracted_items[0].is_dir():
        return extracted_items[0]
    return dest_dir
