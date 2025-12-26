from __future__ import annotations

from io import BytesIO
import zipfile

import pytest

from app.core.kw_zip import KWZipValidationError, validate_kw_zip


def _zip_with_entries(entries: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, contents in entries.items():
            zf.writestr(name, contents)
    return buffer.getvalue()


def test_detects_layout_a_nested_directories() -> None:
    data = _zip_with_entries(
        {
            "GroupA/a1.csv": "a",
            "GroupA/sub/a2.csv": "a2",
            "GroupB/b.csv": "b",
        },
    )
    layout = validate_kw_zip(data)
    assert layout.layout == "A"
    assert {group.name for group in layout.groups} == {"GroupA", "GroupB"}
    assert any("sub/a2.csv" in file for group in layout.groups for file in group.files)


def test_detects_layout_b_and_rejects_nested() -> None:
    flat = _zip_with_entries({"Control.csv": "1", "Variant.csv": "2"})
    layout = validate_kw_zip(flat)
    assert layout.layout == "B"
    assert {group.name for group in layout.groups} == {"Control", "Variant"}

    nested = _zip_with_entries({"Control/file.csv": "1"})
    with pytest.raises(KWZipValidationError):
        validate_kw_zip(nested)


def test_rejects_mixed_layouts() -> None:
    data = _zip_with_entries({"GroupA/a.csv": "a", "root.csv": "b"})
    with pytest.raises(KWZipValidationError) as exc:
        validate_kw_zip(data)
    assert exc.value.code == "MIXED_KW_ZIP_LAYOUT"


def test_rejects_duplicate_group_names_after_sanitization() -> None:
    data = _zip_with_entries({"Group A/a.csv": "a", "Group_A/b.csv": "b"})
    with pytest.raises(KWZipValidationError) as exc:
        validate_kw_zip(data)
    assert exc.value.code == "DUPLICATE_GROUP_NAME"


def test_requires_minimum_groups() -> None:
    data = _zip_with_entries({"Solo.csv": "1"})
    with pytest.raises(KWZipValidationError) as exc:
        validate_kw_zip(data)
    assert exc.value.code == "INSUFFICIENT_GROUPS"
