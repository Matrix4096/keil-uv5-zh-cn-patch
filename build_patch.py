#!/usr/bin/env python3
"""Build a non-destructive Simplified Chinese copy of Arm Keil uVision 5.x.

The original signed executable is never modified.  The fully tested 5.43.1
build is recognized by SHA-256.  Other uVision 5.x builds use a conservative
compatibility mode that changes only entries whose resource identity and
original English text both match the bundled source-only translation catalog.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys

TOOLS_DIR = Path(__file__).resolve().parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from pe_resources import (  # noqa: E402
    RT_MENU,
    RT_STRING,
    parse_string_block,
    read_resources,
    update_resources,
)
from resource_formats import (  # noqa: E402
    parse_menu,
    serialize_menu,
)


TARGET_SHA256 = "428BAF13D15E6760AF1618DEF9C9815C97F0321CC5E459EC7ADC4DDE41C42F89"
ENGLISH_US = 1033
DEFAULT_CATALOG = Path(__file__).resolve().parent / "translations" / "zh_CN.json"
DEFAULT_MIN_COVERAGE = 0.70


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-16le")).hexdigest().upper()


class VSFixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("signature", ctypes.c_uint32),
        ("structure_version", ctypes.c_uint32),
        ("file_version_ms", ctypes.c_uint32),
        ("file_version_ls", ctypes.c_uint32),
        ("product_version_ms", ctypes.c_uint32),
        ("product_version_ls", ctypes.c_uint32),
        ("file_flags_mask", ctypes.c_uint32),
        ("file_flags", ctypes.c_uint32),
        ("file_os", ctypes.c_uint32),
        ("file_type", ctypes.c_uint32),
        ("file_subtype", ctypes.c_uint32),
        ("file_date_ms", ctypes.c_uint32),
        ("file_date_ls", ctypes.c_uint32),
    ]


def file_version(path: Path) -> tuple[int, int, int, int]:
    if os.name != "nt":
        raise SystemExit("This patcher requires Windows.")
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
    version.GetFileVersionInfoSizeW.restype = ctypes.c_uint32
    version.GetFileVersionInfoW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    version.GetFileVersionInfoW.restype = ctypes.c_int
    version.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    version.VerQueryValueW.restype = ctypes.c_int

    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        raise SystemExit(f"No Windows version information found in: {path}")
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    pointer = ctypes.c_void_p()
    length = ctypes.c_uint32()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise ctypes.WinError(ctypes.get_last_error())
    fixed = ctypes.cast(pointer, ctypes.POINTER(VSFixedFileInfo)).contents
    if fixed.signature != 0xFEEF04BD:
        raise SystemExit(f"Invalid Windows version resource in: {path}")
    return (
        fixed.file_version_ms >> 16,
        fixed.file_version_ms & 0xFFFF,
        fixed.file_version_ls >> 16,
        fixed.file_version_ls & 0xFFFF,
    )


def load_catalog(path: Path) -> dict[str, object]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read translation catalog {path}: {error}") from error
    if catalog.get("format_version") != 2:
        raise SystemExit("Unsupported translation catalog format; expected version 2.")
    if int(catalog.get("language", -1)) != ENGLISH_US:
        raise SystemExit("Translation catalog language does not match the target resources.")
    translations = catalog.get("translations")
    if not isinstance(translations, dict):
        raise SystemExit("Translation catalog has no translations object.")
    if not isinstance(translations.get("string_table"), dict) or not isinstance(
        translations.get("menus"), dict
    ):
        raise SystemExit("Translation catalog string_table or menus section is invalid.")
    return catalog


def build_string_block(name: int, values: dict[int, str]) -> bytes:
    output = bytearray()
    base_id = (name - 1) * 16
    for index in range(16):
        encoded = values.get(base_id + index, "").encode("utf-16le")
        length = len(encoded) // 2
        if length > 0xFFFF:
            raise ValueError(f"String {base_id + index} is too long")
        output.extend(struct.pack("<H", length))
        output.extend(encoded)
    return bytes(output)


def translation_pair(entry: object, label: str) -> tuple[str, str]:
    if not isinstance(entry, dict):
        raise SystemExit(f"Invalid catalog entry: {label}")
    source = entry.get("source_sha256")
    translation = entry.get("translation")
    if (
        not isinstance(source, str)
        or len(source) != 64
        or any(character not in "0123456789ABCDEFabcdef" for character in source)
        or not isinstance(translation, str)
        or not translation
    ):
        raise SystemExit(f"Invalid source hash or translation in catalog entry: {label}")
    return source.upper(), translation


def menu_item_at_path(menu: dict[str, object], path: str) -> dict[str, object] | None:
    try:
        indexes = [int(value) for value in path.split("/")]
    except ValueError:
        return None
    items = menu["items"]
    item: dict[str, object] | None = None
    for index in indexes:
        if index < 0 or index >= len(items):
            return None
        item = items[index]
        items = item["children"]
    return item


def plan_updates(
    target: Path, catalog: dict[str, object]
) -> tuple[list[dict[str, object]], dict[str, object]]:
    translations = catalog["translations"]
    string_catalog = translations["string_table"]
    menu_catalog = translations["menus"]
    catalog_strings: dict[int, object] = {}
    catalog_menus: dict[int, dict[str, object]] = {}
    try:
        for key, value in string_catalog.items():
            catalog_strings[int(key)] = value
        for key, value in menu_catalog.items():
            if not isinstance(value, dict):
                raise ValueError(key)
            catalog_menus[int(key)] = value
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Translation catalog contains an invalid resource ID: {error}")

    matched_strings: set[int] = set()
    matched_menus: set[tuple[int, str]] = set()
    updates: list[dict[str, object]] = []
    report: dict[str, object] = {
        "target": str(target),
        "language": ENGLISH_US,
        "string_table": {"resources": 0, "texts": 0},
        "menus": {"resources": 0, "texts": 0},
    }

    for target_item in read_resources(target):
        if int(target_item["lang"]) != ENGLISH_US:
            continue
        resource_name = target_item["name"]

        if target_item["type"] == RT_STRING and isinstance(resource_name, int):
            target_values = parse_string_block(resource_name, target_item["data"])
            changed = 0
            for string_id, current_text in target_values.items():
                entry = catalog_strings.get(string_id)
                if entry is None:
                    continue
                source_hash, translation = translation_pair(entry, f"string {string_id}")
                if text_sha256(current_text) != source_hash:
                    continue
                target_values[string_id] = translation
                matched_strings.add(string_id)
                changed += 1
            if changed:
                updates.append(
                    {
                        "type": RT_STRING,
                        "name": resource_name,
                        "lang": ENGLISH_US,
                        "data": build_string_block(resource_name, target_values),
                    }
                )
                report["string_table"]["resources"] += 1
                report["string_table"]["texts"] += changed

        elif target_item["type"] == RT_MENU and isinstance(resource_name, int):
            entries = catalog_menus.get(resource_name)
            if entries is None:
                continue
            target_menu = parse_menu(target_item["data"])
            changed = 0
            for path, entry in entries.items():
                source_hash, translation = translation_pair(
                    entry, f"menu {resource_name}:{path}"
                )
                item = menu_item_at_path(target_menu, path)
                if item is None or text_sha256(str(item["text"])) != source_hash:
                    continue
                item["text"] = translation
                matched_menus.add((resource_name, path))
                changed += 1
            if changed:
                updates.append(
                    {
                        "type": RT_MENU,
                        "name": resource_name,
                        "lang": ENGLISH_US,
                        "data": serialize_menu(target_menu),
                    }
                )
                report["menus"]["resources"] += 1
                report["menus"]["texts"] += changed

    all_menu_keys = {
        (resource_id, path)
        for resource_id, entries in catalog_menus.items()
        for path in entries
    }
    total = len(catalog_strings) + len(all_menu_keys)
    matched = len(matched_strings) + len(matched_menus)
    report["resource_updates"] = len(updates)
    report["coverage"] = {
        "matched": matched,
        "total": total,
        "ratio": round(matched / total, 6) if total else 0.0,
        "matched_strings": len(matched_strings),
        "total_strings": len(catalog_strings),
        "matched_menu_items": len(matched_menus),
        "total_menu_items": len(all_menu_keys),
        "unmatched_string_ids": sorted(set(catalog_strings) - matched_strings),
        "unmatched_menu_items": [
            f"{resource_id}:{path}"
            for resource_id, path in sorted(all_menu_keys - matched_menus)
        ],
    }
    return updates, report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(
        description=(
            "Create a non-destructive Simplified Chinese copy of uVision 5.x "
            "using a source-validated translation catalog."
        )
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="path to an official uVision 5.x UV4.exe",
    )
    parser.add_argument(
        "--catalog",
        default=DEFAULT_CATALOG,
        type=Path,
        help="translation catalog (default: bundled Simplified Chinese catalog)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="output path (default: UV4_zh-CN.exe beside the target)",
    )
    parser.add_argument(
        "--report",
        default=Path(__file__).resolve().parent / "patch-report.json",
        type=Path,
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=DEFAULT_MIN_COVERAGE,
        help="minimum source-text match ratio for untested uVision 5.x builds",
    )
    parser.add_argument(
        "--exact-only",
        action="store_true",
        help="accept only the fully tested 5.43.1 executable hash",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = args.target.resolve()
    catalog_path = args.catalog.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else target.with_name("UV4_zh-CN.exe")
    )
    report_path = args.report.resolve()
    if not 0.0 <= args.min_coverage <= 1.0:
        raise SystemExit("--min-coverage must be between 0.0 and 1.0.")
    if not target.is_file():
        raise SystemExit(f"Target file does not exist: {target}")
    if output == target:
        raise SystemExit("Output must not overwrite the original UV4.exe.")

    version = file_version(target)
    if version[0] != 5:
        raise SystemExit(
            f"Unsupported file version {'.'.join(map(str, version))}; "
            "only uVision 5.x is accepted. No file was changed."
        )
    target_hash = sha256(target)
    catalog = load_catalog(catalog_path)
    catalog_target = catalog.get("target")
    if not isinstance(catalog_target, dict) or not isinstance(
        catalog_target.get("sha256"), str
    ):
        raise SystemExit("Translation catalog target metadata is invalid.")
    tested_hash = str(catalog_target["sha256"]).upper()
    exact_target = target_hash == tested_hash

    updates, report = plan_updates(target, catalog)
    coverage = float(report["coverage"]["ratio"])
    accepted = exact_target or (
        not args.exact_only and coverage >= args.min_coverage
    )
    mode = "exact-tested" if exact_target else "compatible-source-match"
    report["target_version"] = ".".join(map(str, version))
    report["target_sha256"] = target_hash
    report["catalog"] = str(catalog_path)
    report["catalog_sha256"] = sha256(catalog_path)
    report["compatibility"] = {
        "mode": mode,
        "fully_tested": exact_target,
        "minimum_coverage": args.min_coverage,
        "exact_only": bool(args.exact_only),
        "accepted": accepted,
    }
    report["output"] = str(output)
    report["dry_run"] = bool(args.dry_run)

    if accepted and not args.dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".building")
        if temporary.exists():
            temporary.unlink()
        shutil.copy2(target, temporary)
        try:
            update_resources(temporary, updates)
            os.replace(temporary, output)
        finally:
            if temporary.exists():
                temporary.unlink()
        report["output_sha256"] = sha256(output)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not accepted:
        print(
            "Compatibility check failed: source-text coverage is below the "
            "required threshold, or --exact-only rejected this build. "
            "No executable was generated.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
