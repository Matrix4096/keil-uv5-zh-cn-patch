#!/usr/bin/env python3
"""Compare PE section payloads to prove executable code was not modified."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def sections(path: Path) -> dict[str, dict[str, object]]:
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError(f"Not a PE file: {path}")
    pe_offset = struct.unpack_from("<L", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError(f"PE signature not found: {path}")
    section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    table = pe_offset + 24 + optional_size
    result: dict[str, dict[str, object]] = {}
    for index in range(section_count):
        offset = table + index * 40
        name = data[offset : offset + 8].split(b"\0", 1)[0].decode("ascii")
        raw_size, raw_offset = struct.unpack_from("<LL", data, offset + 16)
        payload = data[raw_offset : raw_offset + raw_size]
        result[name] = {
            "size": raw_size,
            "sha256": hashlib.sha256(payload).hexdigest().upper(),
        }
    return result


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_pe_sections.py ORIGINAL PATCHED")
    original = Path(sys.argv[1]).resolve()
    patched = Path(sys.argv[2]).resolve()
    left = sections(original)
    right = sections(patched)
    names = sorted(left.keys() | right.keys())
    comparison = {
        name: {
            "original": left.get(name),
            "patched": right.get(name),
            "identical": left.get(name) == right.get(name),
        }
        for name in names
    }
    payload = {
        "original": str(original),
        "patched": str(patched),
        "sections": comparison,
        "code_sections_identical": all(
            comparison.get(name, {}).get("identical", False)
            for name in (".text", ".data", ".rdata")
            if name in comparison
        ),
        "resource_section_changed": not comparison.get(".rsrc", {}).get(
            "identical", True
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["code_sections_identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
