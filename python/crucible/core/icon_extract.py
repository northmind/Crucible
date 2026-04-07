"""Pure-Python icon extraction from PE (.exe) files.

Parses the PE resource table to locate RT_GROUP_ICON / RT_ICON entries,
reconstructs a valid .ico stream, and uses Pillow to convert to PNG.

This module is a fallback for when ``wrestool`` / ``icotool`` (from the
*icoutils* package) are not available on the host.  The CLI tools are
preferred when present because they handle more edge-cases in malformed
PE binaries.
"""

from __future__ import annotations

import io
import logging
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

# PE resource type IDs
_RT_ICON = 3
_RT_GROUP_ICON = 14


# ---------------------------------------------------------------------------
# Low-level PE helpers
# ---------------------------------------------------------------------------

def _read_u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def _read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _rva_to_offset(rva: int, sections: list[tuple[int, int, int, int]]) -> int | None:
    """Convert a Relative Virtual Address to a file offset using section table."""
    for va, va_size, raw_off, raw_size in sections:
        if va <= rva < va + va_size:
            return raw_off + (rva - va)
    return None


def _parse_sections(data: bytes, pe_off: int, num_sections: int) -> list[tuple[int, int, int, int]]:
    """Parse the section table.  Returns list of (VirtualAddress, VirtualSize, RawOffset, RawSize)."""
    # Optional header size is at PE+20
    opt_size = _read_u16(data, pe_off + 20)
    section_off = pe_off + 24 + opt_size
    sections = []
    for i in range(num_sections):
        s = section_off + i * 40
        va_size = _read_u32(data, s + 8)
        va = _read_u32(data, s + 12)
        raw_size = _read_u32(data, s + 16)
        raw_off = _read_u32(data, s + 20)
        sections.append((va, va_size, raw_off, raw_size))
    return sections


def _walk_resource_dir(
    data: bytes,
    rsrc_offset: int,
    rsrc_rva: int,
    dir_offset: int,
    depth: int,
    path: tuple[int, ...],
    results: dict[tuple[int, ...], int],
) -> None:
    """Recursively walk a PE IMAGE_RESOURCE_DIRECTORY tree.

    ``results`` maps (type_id, name_id, lang_id) -> file offset of data.
    """
    if depth > 3:
        return
    base = rsrc_offset + dir_offset
    if base + 16 > len(data):
        return
    num_named = _read_u16(data, base + 12)
    num_id = _read_u16(data, base + 14)
    entry_off = base + 16
    for _ in range(num_named + num_id):
        if entry_off + 8 > len(data):
            return
        name_or_id = _read_u32(data, entry_off)
        offset_to_data = _read_u32(data, entry_off + 4)
        entry_off += 8

        # High bit set on name_or_id means it's a named entry — use 0 as id
        eid = 0 if name_or_id & 0x80000000 else name_or_id

        if offset_to_data & 0x80000000:
            # Points to a subdirectory
            sub_dir_off = offset_to_data & 0x7FFFFFFF
            _walk_resource_dir(data, rsrc_offset, rsrc_rva, sub_dir_off, depth + 1, path + (eid,), results)
        else:
            # Points to a data entry (IMAGE_RESOURCE_DATA_ENTRY)
            de_off = rsrc_offset + (offset_to_data & 0x7FFFFFFF)
            if de_off + 16 <= len(data):
                data_rva = _read_u32(data, de_off)
                data_size = _read_u32(data, de_off + 4)
                # Convert RVA to file offset relative to rsrc section
                file_off = rsrc_offset + (data_rva - rsrc_rva)
                if 0 <= file_off < len(data) and file_off + data_size <= len(data):
                    results[path + (eid,)] = (file_off, data_size)


# ---------------------------------------------------------------------------
# ICO reconstruction
# ---------------------------------------------------------------------------

def _build_ico(
    group_data: bytes,
    icon_entries: dict[int, tuple[int, int]],
    pe_data: bytes,
) -> bytes | None:
    """Reconstruct a .ico file from a GRPICONDIR header and individual RT_ICON blobs.

    ``group_data`` is the raw RT_GROUP_ICON resource.
    ``icon_entries`` maps icon ordinal -> (file_offset, size) in pe_data.
    """
    if len(group_data) < 6:
        return None
    count = _read_u16(group_data, 4)
    if len(group_data) < 6 + count * 14:
        return None

    # ICO header: reserved(2) + type(2) + count(2) = 6 bytes
    # Each ICO directory entry: 16 bytes (vs 14 in the group)
    header = struct.pack('<HHH', 0, 1, count)
    entries_buf = io.BytesIO()
    image_buf = io.BytesIO()
    data_offset = 6 + count * 16  # offset where image data starts

    for i in range(count):
        ge = 6 + i * 14  # GRPICONDIRENTRY offset
        width = group_data[ge]
        height = group_data[ge + 1]
        color_count = group_data[ge + 2]
        reserved = group_data[ge + 3]
        planes = _read_u16(group_data, ge + 4)
        bit_count = _read_u16(group_data, ge + 6)
        byte_size = _read_u32(group_data, ge + 8)
        ordinal = _read_u16(group_data, ge + 12)

        entry = icon_entries.get(ordinal)
        if entry is None:
            continue
        img_offset, img_size = entry
        img_data = pe_data[img_offset:img_offset + img_size]

        entries_buf.write(struct.pack(
            '<BBBBHHII',
            width, height, color_count, reserved,
            planes, bit_count, len(img_data),
            data_offset + image_buf.tell(),
        ))
        image_buf.write(img_data)

    result = header + entries_buf.getvalue() + image_buf.getvalue()
    return result if len(result) > 6 else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_icon_to_png(exe_path: str, output_path: Path) -> bool:
    """Extract the largest icon from *exe_path* and save as PNG to *output_path*.

    Returns ``True`` on success.  On any parse failure the function returns
    ``False`` without raising.
    """
    try:
        data = Path(exe_path).read_bytes()
    except OSError as exc:
        logger.debug("Cannot read exe %s: %s", exe_path, exc)
        return False

    try:
        return _extract(data, output_path)
    except Exception as exc:  # noqa: BLE001 — defensive against malformed PE
        logger.debug("PE icon extraction failed for %s: %s", exe_path, exc)
        return False


def _extract(data: bytes, output_path: Path) -> bool:
    # ---- Validate DOS / PE headers ----
    if len(data) < 64 or data[:2] != b'MZ':
        return False
    pe_off = _read_u32(data, 0x3C)
    if pe_off + 24 > len(data) or data[pe_off:pe_off + 4] != b'PE\x00\x00':
        return False

    # COFF header
    num_sections = _read_u16(data, pe_off + 6)
    opt_size = _read_u16(data, pe_off + 20)
    opt_off = pe_off + 24

    # Determine PE32 vs PE32+
    magic = _read_u16(data, opt_off)
    if magic == 0x20B:  # PE32+
        data_dir_off = opt_off + 112
    elif magic == 0x10B:  # PE32
        data_dir_off = opt_off + 96
    else:
        return False

    num_rva_sizes = _read_u32(data, data_dir_off - 4) if data_dir_off >= opt_off + 4 else 0
    # Resource table is data directory index 2
    if num_rva_sizes < 3:
        return False
    rsrc_dir_entry = data_dir_off + 2 * 8  # each data dir entry is 8 bytes
    if rsrc_dir_entry + 8 > len(data):
        return False
    rsrc_rva = _read_u32(data, rsrc_dir_entry)
    rsrc_size = _read_u32(data, rsrc_dir_entry + 4)
    if rsrc_rva == 0 or rsrc_size == 0:
        return False

    sections = _parse_sections(data, pe_off, num_sections)
    rsrc_offset = _rva_to_offset(rsrc_rva, sections)
    if rsrc_offset is None:
        return False

    # ---- Walk resource tree ----
    resources: dict[tuple[int, ...], tuple[int, int]] = {}
    _walk_resource_dir(data, rsrc_offset, rsrc_rva, 0, 0, (), resources)

    # Collect RT_GROUP_ICON entries
    group_icons = {k: v for k, v in resources.items() if len(k) >= 1 and k[0] == _RT_GROUP_ICON}
    if not group_icons:
        return False

    # Collect RT_ICON entries keyed by ordinal
    icon_entries: dict[int, tuple[int, int]] = {}
    for k, v in resources.items():
        if len(k) >= 2 and k[0] == _RT_ICON:
            icon_entries[k[1]] = v

    if not icon_entries:
        return False

    # ---- Pick the best group and build the .ico ----
    # Try each group icon; pick the one that yields the largest image
    best_ico: bytes | None = None
    for _key, (g_off, g_size) in group_icons.items():
        group_data = data[g_off:g_off + g_size]
        ico = _build_ico(group_data, icon_entries, data)
        if ico and (best_ico is None or len(ico) > len(best_ico)):
            best_ico = ico

    if best_ico is None:
        return False

    # ---- Convert .ico -> .png via Pillow ----
    try:
        from PIL import Image
    except ImportError:
        logger.debug("Pillow not available for ICO->PNG conversion")
        return False

    try:
        img = Image.open(io.BytesIO(best_ico))
        # If the ICO has multiple sizes, pick the largest
        if hasattr(img, 'size'):
            sizes = getattr(img.info, 'sizes', None)
            # ICO files via Pillow: use .ico attribute to get sizes
            pass
        # For multi-size ICOs, Pillow opens the largest by default
        # Ensure RGBA for clean PNG
        img = img.convert('RGBA')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), 'PNG')
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Pillow ICO->PNG conversion failed: %s", exc)
        return False
