#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from pe_resources import RT_DIALOG, RT_MENU, read_resources
from resource_formats import (
    parse_dialog,
    parse_menu,
    serialize_dialog,
    serialize_menu,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def validate(path: Path) -> dict[str, object]:
    stats: dict[str, object] = {
        "path": str(path),
        "menu": {"total": 0, "exact": 0, "mismatch": [], "errors": []},
        "dialog": {"total": 0, "exact": 0, "mismatch": [], "errors": []},
    }
    for resource in read_resources(path):
        if resource["type"] == RT_MENU:
            bucket = stats["menu"]
            parser, serializer = parse_menu, serialize_menu
        elif resource["type"] == RT_DIALOG:
            bucket = stats["dialog"]
            parser, serializer = parse_dialog, serialize_dialog
        else:
            continue
        bucket["total"] += 1
        label = f"{resource['name']}:{resource['lang']}"
        try:
            rebuilt = serializer(parser(resource["data"]))
            if rebuilt == resource["data"]:
                bucket["exact"] += 1
            else:
                bucket["mismatch"].append(
                    {
                        "resource": label,
                        "original": len(resource["data"]),
                        "rebuilt": len(rebuilt),
                    }
                )
        except Exception as error:
            bucket["errors"].append({"resource": label, "error": str(error)})
    return stats


def main() -> int:
    reports = [validate(Path(argument).resolve()) for argument in sys.argv[1:]]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
