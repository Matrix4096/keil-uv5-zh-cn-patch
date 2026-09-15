#!/usr/bin/env python3
"""Build a non-destructive Simplified Chinese copy of uVision 5.43.1.

The original signed executable is never modified.  This tool validates both
the exact target build and the known 5.25.3 translation donor by SHA-256,
copies the target, and updates display-only Win32 resources in that copy.
"""

from __future__ import annotations

import argparse
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
    RT_DIALOG,
    RT_MENU,
    RT_STRING,
    has_cjk,
    parse_string_block,
    read_resources,
    update_resources,
)
from resource_formats import (  # noqa: E402
    dialog_skeleton,
    menu_skeleton,
    parse_dialog,
    parse_menu,
    serialize_dialog,
    serialize_menu,
    translate_dialog,
    translate_menu,
)


TARGET_SHA256 = "428BAF13D15E6760AF1618DEF9C9815C97F0321CC5E459EC7ADC4DDE41C42F89"
DONOR_SHA256 = "AEF83B317826FEA7149946030808A2A9D34038446D621E5C514C31A450B3AB79"
ENGLISH_US = 1033


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_file(path: Path, expected: str, label: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(
            f"{label} SHA-256 mismatch.\nExpected: {expected}\nActual:   {actual}\n"
            "No file was changed."
        )


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


def resource_index(resources: list[dict[str, object]]) -> dict[tuple[object, object, int], dict[str, object]]:
    return {
        (item["type"], item["name"], int(item["lang"])): item
        for item in resources
    }


def plan_updates(target: Path, donor: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    target_resources = read_resources(target)
    donor_resources = read_resources(donor)
    donor_index = resource_index(donor_resources)
    updates: list[dict[str, object]] = []
    report: dict[str, object] = {
        "target": str(target),
        "donor": str(donor),
        "language": ENGLISH_US,
        "string_table": {"resources": 0, "texts": 0},
        "menus": {"resources": 0, "texts": 0, "skipped_structure_mismatch": []},
        "dialogs": {
            "resources": 0,
            "texts": 0,
            "exact_structure": 0,
            "compatible_partial_structure": 0,
        },
    }

    for target_item in target_resources:
        if int(target_item["lang"]) != ENGLISH_US:
            continue
        donor_item = donor_index.get(
            (target_item["type"], target_item["name"], ENGLISH_US)
        )
        if donor_item is None:
            continue

        if target_item["type"] == RT_STRING:
            if not isinstance(target_item["name"], int):
                continue
            target_values = parse_string_block(target_item["name"], target_item["data"])
            donor_values = parse_string_block(donor_item["name"], donor_item["data"])
            changed = 0
            for string_id in target_values.keys() & donor_values.keys():
                if target_values[string_id] and donor_values[string_id] and has_cjk(
                    donor_values[string_id]
                ):
                    target_values[string_id] = donor_values[string_id]
                    changed += 1
            if changed:
                updates.append(
                    {
                        "type": RT_STRING,
                        "name": target_item["name"],
                        "lang": ENGLISH_US,
                        "data": build_string_block(target_item["name"], target_values),
                    }
                )
                report["string_table"]["resources"] += 1
                report["string_table"]["texts"] += changed

        elif target_item["type"] == RT_MENU:
            target_menu = parse_menu(target_item["data"])
            donor_menu = parse_menu(donor_item["data"])
            if menu_skeleton(target_menu) != menu_skeleton(donor_menu):
                report["menus"]["skipped_structure_mismatch"].append(
                    target_item["name"]
                )
                continue
            translated, changed = translate_menu(target_menu, donor_menu, has_cjk)
            if changed:
                updates.append(
                    {
                        "type": RT_MENU,
                        "name": target_item["name"],
                        "lang": ENGLISH_US,
                        "data": serialize_menu(translated),
                    }
                )
                report["menus"]["resources"] += 1
                report["menus"]["texts"] += changed

        elif target_item["type"] == RT_DIALOG:
            target_dialog = parse_dialog(target_item["data"])
            donor_dialog = parse_dialog(donor_item["data"])
            exact = dialog_skeleton(target_dialog) == dialog_skeleton(donor_dialog)
            translated, changed = translate_dialog(target_dialog, donor_dialog, has_cjk)
            if changed:
                updates.append(
                    {
                        "type": RT_DIALOG,
                        "name": target_item["name"],
                        "lang": ENGLISH_US,
                        "data": serialize_dialog(translated),
                    }
                )
                report["dialogs"]["resources"] += 1
                report["dialogs"]["texts"] += changed
                key = "exact_structure" if exact else "compatible_partial_structure"
                report["dialogs"][key] += 1

    report["resource_updates"] = len(updates)
    return updates, report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(
        description=(
            "Create a non-destructive Simplified Chinese copy of the exact "
            "supported uVision 5.43.1 executable."
        )
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="path to the official uVision 5.43.1 UV4.exe",
    )
    parser.add_argument(
        "--donor",
        required=True,
        type=Path,
        help="path to the user-supplied 5.25.3 translation donor",
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = args.target.resolve()
    donor = args.donor.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else target.with_name("UV4_zh-CN.exe")
    )
    report_path = args.report.resolve()
    validate_file(target, TARGET_SHA256, "Target uVision")
    validate_file(donor, DONOR_SHA256, "Translation donor")

    updates, report = plan_updates(target, donor)
    report["target_sha256"] = TARGET_SHA256
    report["donor_sha256"] = DONOR_SHA256
    report["output"] = str(output)
    report["dry_run"] = bool(args.dry_run)

    if not args.dry_run:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
