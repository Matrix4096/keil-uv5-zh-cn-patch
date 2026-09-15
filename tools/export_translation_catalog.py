#!/usr/bin/env python3
"""Export a source-only translation catalog from two compatible PE files.

This is a maintainer utility.  It records only translated UI text, keyed by
stable Win32 resource identifiers and menu item paths; no executable bytes are
embedded in the resulting JSON file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from pe_resources import RT_MENU, RT_STRING, has_cjk, parse_string_block, read_resources
from resource_formats import menu_skeleton, parse_menu


TARGET_SHA256 = "428BAF13D15E6760AF1618DEF9C9815C97F0321CC5E459EC7ADC4DDE41C42F89"
PATCHED_SHA256 = "7FDF1F2F48763B003862740F25CB306A20ED9D40772FCB1E8D8F2B1E839114CD"
ENGLISH_US = 1033


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-16le")).hexdigest().upper()


def require_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(
            f"{label} SHA-256 mismatch.\nExpected: {expected}\nActual:   {actual}"
        )


def index_resources(path: Path) -> dict[tuple[object, object, int], dict[str, object]]:
    return {
        (item["type"], item["name"], int(item["lang"])): item
        for item in read_resources(path)
    }


def menu_differences(
    original: dict[str, object], translated: dict[str, object]
) -> dict[str, dict[str, str]]:
    if menu_skeleton(original) != menu_skeleton(translated):
        raise ValueError("Menu structures differ")
    result: dict[str, dict[str, str]] = {}

    def walk(
        left: list[dict[str, object]],
        right: list[dict[str, object]],
        prefix: tuple[int, ...] = (),
    ) -> None:
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            path = prefix + (index,)
            left_text = str(left_item["text"])
            right_text = str(right_item["text"])
            if left_text != right_text:
                if not right_text or not has_cjk(right_text):
                    raise ValueError(
                        f"Changed menu text at {'/'.join(map(str, path))} is not Chinese"
                    )
                result["/".join(map(str, path))] = {
                    "source_sha256": text_sha256(left_text),
                    "translation": right_text,
                }
            walk(left_item["children"], right_item["children"], path)

    walk(original["items"], translated["items"])
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path)
    parser.add_argument("patched", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    original = args.original.resolve()
    patched = args.patched.resolve()
    output = args.output.resolve()
    require_hash(original, TARGET_SHA256, "Original uVision")
    require_hash(patched, PATCHED_SHA256, "Patched uVision")

    left = index_resources(original)
    right = index_resources(patched)
    strings: dict[str, dict[str, str]] = {}
    menus: dict[str, dict[str, dict[str, str]]] = {}
    string_blocks: set[int] = set()

    for key, original_item in left.items():
        resource_type, resource_name, language = key
        if language != ENGLISH_US or key not in right:
            continue
        patched_item = right[key]
        if resource_type == RT_STRING and isinstance(resource_name, int):
            original_values = parse_string_block(resource_name, original_item["data"])
            patched_values = parse_string_block(resource_name, patched_item["data"])
            for string_id in sorted(original_values.keys() & patched_values.keys()):
                translated = patched_values[string_id]
                if original_values[string_id] != translated:
                    if not translated or not has_cjk(translated):
                        raise ValueError(
                            f"Changed string {string_id} is not a Chinese translation"
                        )
                    strings[str(string_id)] = {
                        "source_sha256": text_sha256(original_values[string_id]),
                        "translation": translated,
                    }
                    string_blocks.add(resource_name)
        elif resource_type == RT_MENU and isinstance(resource_name, int):
            changes = menu_differences(
                parse_menu(original_item["data"]),
                parse_menu(patched_item["data"]),
            )
            if changes:
                menus[str(resource_name)] = changes

    catalog = {
        "format_version": 2,
        "language": ENGLISH_US,
        "target": {
            "product": "Arm Keil µVision",
            "version": "5.43.1.0",
            "sha256": TARGET_SHA256,
        },
        "translations": {
            "string_table": strings,
            "menus": menus,
        },
        "stats": {
            "string_resources": len(string_blocks),
            "strings": len(strings),
            "menu_resources": len(menus),
            "menu_items": sum(len(items) for items in menus.values()),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(catalog["stats"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
