from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from typing import Iterable


class KWZipValidationError(ValueError):
    """Raised when a KW permutation ZIP fails validation."""

    def __init__(self, code: str, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class KWGroup:
    name: str
    files: list[str]


@dataclass(frozen=True)
class KWZipLayout:
    layout: str
    groups: list[KWGroup]


IGNORED_PREFIXES = ("__MACOSX/", ".")


def _sanitize_group_name(name: str) -> str:
    trimmed = name.strip()
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", trimmed)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized[:64]


def _iter_csv_entries(zf: zipfile.ZipFile) -> Iterable[zipfile.ZipInfo]:
    for info in zf.infolist():
        if info.is_dir():
            continue
        if info.filename.startswith(IGNORED_PREFIXES):
            continue
        path = PurePath(info.filename)
        if any(part.startswith(".") for part in path.parts):
            continue
        if path.suffix.lower() == ".csv":
            yield info


def validate_kw_zip(raw_bytes: bytes) -> KWZipLayout:
    try:
        zf = zipfile.ZipFile(BytesIO(raw_bytes))
    except zipfile.BadZipFile as exc:
        raise KWZipValidationError("INVALID_ZIP", "kwBundle must be a valid ZIP archive.") from exc

    csv_entries = list(_iter_csv_entries(zf))
    if not csv_entries:
        raise KWZipValidationError("INVALID_KW_ZIP_LAYOUT", "ZIP must include at least two CSV files.")

    has_folder_csv = any(len(PurePath(info.filename).parts) > 1 for info in csv_entries)
    has_root_csv = any(len(PurePath(info.filename).parts) == 1 for info in csv_entries)

    if has_folder_csv and has_root_csv:
        raise KWZipValidationError("MIXED_KW_ZIP_LAYOUT", "Do not mix root-level CSVs with grouped folders.")

    layout: str
    groups: dict[str, list[str]] = {}

    normalized_sources: dict[str, str] = {}

    if has_folder_csv:
        layout = "A"
        for info in csv_entries:
            path = PurePath(info.filename)
            group_raw = path.parts[0]
            group = _sanitize_group_name(group_raw)
            normalized = group.lower()
            previous_source = normalized_sources.get(normalized)
            if previous_source is not None and previous_source != group_raw:
                raise KWZipValidationError("DUPLICATE_GROUP_NAME", "Group names collide after sanitization.")
            normalized_sources.setdefault(normalized, group_raw)
            groups.setdefault(group, []).append(info.filename)
    else:
        layout = "B"
        for info in csv_entries:
            path = PurePath(info.filename)
            if len(path.parts) > 1:
                raise KWZipValidationError(
                    "INVALID_KW_ZIP_LAYOUT",
                    "Nested folders are not allowed for flat KW ZIP layout.",
                )
            group = _sanitize_group_name(path.stem)
            normalized = group.lower()
            previous_source = normalized_sources.get(normalized)
            if previous_source is not None and previous_source != path.stem:
                raise KWZipValidationError("DUPLICATE_GROUP_NAME", "Group names collide after sanitization.")
            normalized_sources.setdefault(normalized, path.stem)
            groups.setdefault(group, []).append(info.filename)

    _ensure_group_rules(groups)

    return KWZipLayout(
        layout=layout,
        groups=[KWGroup(name=group, files=sorted(files)) for group, files in sorted(groups.items())],
    )


def _ensure_group_rules(groups: dict[str, list[str]]) -> None:
    if any(not key for key in groups):
        raise KWZipValidationError("INVALID_GROUP_NAME", "Group names cannot be empty after sanitization.")
    normalized_keys = [key.lower() for key in groups]
    if len(set(normalized_keys)) != len(groups):
        raise KWZipValidationError("DUPLICATE_GROUP_NAME", "Group names collide after sanitization.")

    if len(groups) < 2:
        raise KWZipValidationError("INSUFFICIENT_GROUPS", "At least two groups are required.")

    empty_groups = [name for name, files in groups.items() if len(files) == 0]
    if empty_groups:
        raise KWZipValidationError(
            "EMPTY_GROUP",
            "Each group must include at least one CSV file.",
            details={"groups": empty_groups},
        )
