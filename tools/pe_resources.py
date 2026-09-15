#!/usr/bin/env python3
"""Inspect Win32 PE resources without executing the target program.

This utility intentionally uses only the Windows resource APIs and Python's
standard library.  It is the analysis layer for the version-bound uVision
localization patch in this directory.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import struct
import sys
from pathlib import Path


if sys.platform != "win32":
    raise SystemExit("This tool must run on Windows.")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


LOAD_LIBRARY_AS_DATAFILE = 0x00000002
LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020
RT_MENU = 4
RT_DIALOG = 5
RT_STRING = 6

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

kernel32.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
kernel32.LoadLibraryExW.restype = wintypes.HMODULE
kernel32.FreeLibrary.argtypes = [wintypes.HMODULE]
kernel32.FreeLibrary.restype = wintypes.BOOL

ENUMRESTYPEPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p, ctypes.c_ssize_t
)
ENUMRESNAMEPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMODULE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_ssize_t,
)
ENUMRESLANGPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMODULE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.WORD,
    ctypes.c_ssize_t,
)

kernel32.EnumResourceTypesW.argtypes = [wintypes.HMODULE, ENUMRESTYPEPROC, ctypes.c_ssize_t]
kernel32.EnumResourceTypesW.restype = wintypes.BOOL
kernel32.EnumResourceNamesW.argtypes = [
    wintypes.HMODULE,
    ctypes.c_void_p,
    ENUMRESNAMEPROC,
    ctypes.c_ssize_t,
]
kernel32.EnumResourceNamesW.restype = wintypes.BOOL
kernel32.EnumResourceLanguagesW.argtypes = [
    wintypes.HMODULE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ENUMRESLANGPROC,
    ctypes.c_ssize_t,
]
kernel32.EnumResourceLanguagesW.restype = wintypes.BOOL

kernel32.FindResourceExW.argtypes = [
    wintypes.HMODULE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.WORD,
]
kernel32.FindResourceExW.restype = wintypes.HRSRC
kernel32.LoadResource.argtypes = [wintypes.HMODULE, wintypes.HRSRC]
kernel32.LoadResource.restype = wintypes.HGLOBAL
kernel32.SizeofResource.argtypes = [wintypes.HMODULE, wintypes.HRSRC]
kernel32.SizeofResource.restype = wintypes.DWORD
kernel32.LockResource.argtypes = [wintypes.HGLOBAL]
kernel32.LockResource.restype = ctypes.c_void_p
kernel32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
kernel32.BeginUpdateResourceW.restype = wintypes.HANDLE
kernel32.UpdateResourceW.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.WORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
kernel32.UpdateResourceW.restype = wintypes.BOOL
kernel32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
kernel32.EndUpdateResourceW.restype = wintypes.BOOL


def _raise_last_error(label: str) -> None:
    code = ctypes.get_last_error()
    raise OSError(code, f"{label}: {ctypes.FormatError(code)}")


def _decode_identifier(pointer: int | None) -> int | str:
    value = int(pointer or 0)
    if value <= 0xFFFF:
        return value
    return ctypes.wstring_at(value)


class _IdentifierArg:
    def __init__(self, value: int | str):
        self.value = value
        self.storage: ctypes.c_wchar_p | None = None

    def __enter__(self) -> ctypes.c_void_p:
        if isinstance(self.value, int):
            return ctypes.c_void_p(self.value)
        self.storage = ctypes.c_wchar_p(self.value)
        return ctypes.cast(self.storage, ctypes.c_void_p)

    def __exit__(self, *_: object) -> None:
        self.storage = None


def _resource_key(item: dict[str, object]) -> tuple[str, str, int]:
    return (str(item["type"]), str(item["name"]), int(item["lang"]))


def read_resources(path: Path) -> list[dict[str, object]]:
    module = kernel32.LoadLibraryExW(
        str(path), None, LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE
    )
    if not module:
        _raise_last_error(f"LoadLibraryExW({path})")

    resources: list[dict[str, object]] = []
    callback_refs: list[object] = []

    def on_type(hmod: int, type_ptr: int, _lparam: int) -> bool:
        resource_type = _decode_identifier(type_ptr)

        def on_name(_hmod: int, _type_ptr: int, name_ptr: int, _lp: int) -> bool:
            resource_name = _decode_identifier(name_ptr)

            def on_lang(
                __hmod: int,
                __type_ptr: int,
                __name_ptr: int,
                language: int,
                __lp: int,
            ) -> bool:
                with _IdentifierArg(resource_type) as type_arg, _IdentifierArg(
                    resource_name
                ) as name_arg:
                    hrsrc = kernel32.FindResourceExW(
                        module, type_arg, name_arg, language
                    )
                    if not hrsrc:
                        _raise_last_error("FindResourceExW")
                    size = int(kernel32.SizeofResource(module, hrsrc))
                    hglobal = kernel32.LoadResource(module, hrsrc)
                    if not hglobal:
                        _raise_last_error("LoadResource")
                    pointer = kernel32.LockResource(hglobal)
                    if not pointer and size:
                        _raise_last_error("LockResource")
                    data = ctypes.string_at(pointer, size) if size else b""
                resources.append(
                    {
                        "type": resource_type,
                        "name": resource_name,
                        "lang": int(language),
                        "size": size,
                        "data": data,
                    }
                )
                return True

            language_callback = ENUMRESLANGPROC(on_lang)
            callback_refs.append(language_callback)
            with _IdentifierArg(resource_type) as type_arg, _IdentifierArg(
                resource_name
            ) as name_arg:
                if not kernel32.EnumResourceLanguagesW(
                    module, type_arg, name_arg, language_callback, 0
                ):
                    _raise_last_error("EnumResourceLanguagesW")
            return True

        name_callback = ENUMRESNAMEPROC(on_name)
        callback_refs.append(name_callback)
        with _IdentifierArg(resource_type) as type_arg:
            if not kernel32.EnumResourceNamesW(module, type_arg, name_callback, 0):
                _raise_last_error("EnumResourceNamesW")
        return True

    type_callback = ENUMRESTYPEPROC(on_type)
    callback_refs.append(type_callback)
    try:
        if not kernel32.EnumResourceTypesW(module, type_callback, 0):
            _raise_last_error("EnumResourceTypesW")
    finally:
        kernel32.FreeLibrary(module)
    resources.sort(key=_resource_key)
    return resources


def update_resources(path: Path, updates: list[dict[str, object]]) -> None:
    handle = kernel32.BeginUpdateResourceW(str(path), False)
    if not handle:
        _raise_last_error(f"BeginUpdateResourceW({path})")
    discard = True
    try:
        for item in updates:
            data = bytes(item["data"])
            buffer = ctypes.create_string_buffer(data) if data else None
            pointer = ctypes.cast(buffer, ctypes.c_void_p) if buffer is not None else None
            with _IdentifierArg(item["type"]) as type_arg, _IdentifierArg(
                item["name"]
            ) as name_arg:
                if not kernel32.UpdateResourceW(
                    handle,
                    type_arg,
                    name_arg,
                    int(item["lang"]),
                    pointer,
                    len(data),
                ):
                    _raise_last_error(
                        f"UpdateResourceW({item['type']}, {item['name']}, {item['lang']})"
                    )
        discard = False
    finally:
        if not kernel32.EndUpdateResourceW(handle, discard):
            _raise_last_error("EndUpdateResourceW")


def has_cjk(text: str) -> bool:
    return any(
        "\u3400" <= char <= "\u4dbf" or "\u4e00" <= char <= "\u9fff"
        for char in text
    )


def parse_string_block(name: int | str, data: bytes) -> dict[int, str]:
    if not isinstance(name, int):
        return {}
    output: dict[int, str] = {}
    offset = 0
    base_id = (name - 1) * 16
    for index in range(16):
        if offset + 2 > len(data):
            break
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        byte_length = length * 2
        if offset + byte_length > len(data):
            break
        output[base_id + index] = data[offset : offset + byte_length].decode(
            "utf-16le", errors="replace"
        )
        offset += byte_length
    return output


def extract_utf16_strings(data: bytes, minimum: int = 2) -> list[str]:
    """Extract likely UI strings while ignoring most binary structure words."""
    strings: list[str] = []
    current: list[str] = []
    for offset in range(0, len(data) - 1, 2):
        value = struct.unpack_from("<H", data, offset)[0]
        char = chr(value)
        printable = (
            value == 9
            or 0x20 <= value <= 0x7E
            or 0x00A0 <= value <= 0x02FF
            or 0x3000 <= value <= 0x9FFF
        )
        if printable:
            current.append(char)
        elif value == 0:
            if len(current) >= minimum:
                strings.append("".join(current))
            current = []
        else:
            current = []
    return strings


def summarize(path: Path) -> dict[str, object]:
    resources = read_resources(path)
    by_type: dict[str, dict[str, int]] = {}
    string_values: dict[int, str] = {}
    string_values_by_lang: dict[int, dict[int, str]] = {}
    cjk_samples: list[str] = []
    for item in resources:
        key = str(item["type"])
        entry = by_type.setdefault(key, {"count": 0, "bytes": 0})
        entry["count"] += 1
        entry["bytes"] += int(item["size"])
        if item["type"] == RT_STRING:
            parsed = parse_string_block(item["name"], item["data"])
            string_values.update(parsed)
            string_values_by_lang.setdefault(int(item["lang"]), {}).update(parsed)
        for value in extract_utf16_strings(item["data"]):
            if has_cjk(value) and value not in cjk_samples and len(cjk_samples) < 30:
                cjk_samples.append(value)
    return {
        "path": str(path),
        "resource_count": len(resources),
        "types": by_type,
        "string_table_nonempty": sum(bool(v) for v in string_values.values()),
        "string_table_cjk": sum(has_cjk(v) for v in string_values.values()),
        "string_tables_by_language": {
            str(language): {
                "nonempty": sum(bool(value) for value in values.values()),
                "cjk": sum(has_cjk(value) for value in values.values()),
                "sample": [
                    {"id": string_id, "text": value}
                    for string_id, value in values.items()
                    if value and has_cjk(value)
                ][:12],
            }
            for language, values in sorted(string_values_by_lang.items())
        },
        "cjk_samples": cjk_samples,
    }


def compare(target_path: Path, donor_path: Path) -> dict[str, object]:
    target_resources = read_resources(target_path)
    donor_resources = read_resources(donor_path)
    target_strings_by_lang: dict[int, dict[int, str]] = {}
    donor_strings_by_lang: dict[int, dict[int, str]] = {}
    for item in target_resources:
        if item["type"] == RT_STRING:
            target_strings_by_lang.setdefault(int(item["lang"]), {}).update(
                parse_string_block(item["name"], item["data"])
            )
    for item in donor_resources:
        if item["type"] == RT_STRING:
            donor_strings_by_lang.setdefault(int(item["lang"]), {}).update(
                parse_string_block(item["name"], item["data"])
            )

    target_language = max(
        target_strings_by_lang,
        key=lambda language: sum(
            bool(value) and not has_cjk(value)
            for value in target_strings_by_lang[language].values()
        ),
    )
    donor_language = max(
        donor_strings_by_lang,
        key=lambda language: sum(
            has_cjk(value) for value in donor_strings_by_lang[language].values()
        ),
    )
    target_strings = target_strings_by_lang[target_language]
    donor_strings = donor_strings_by_lang[donor_language]

    candidates = []
    for string_id in sorted(target_strings.keys() & donor_strings.keys()):
        target_value = target_strings[string_id]
        donor_value = donor_strings[string_id]
        if target_value and donor_value and has_cjk(donor_value):
            candidates.append(
                {
                    "id": string_id,
                    "target": target_value,
                    "donor": donor_value,
                    "fits_in_place": len(donor_value) <= len(target_value),
                }
            )

    target_keys = {_resource_key(item) for item in target_resources}
    donor_keys = {_resource_key(item) for item in donor_resources}
    common_keys = target_keys & donor_keys
    common_by_type: dict[str, int] = {}
    for resource_type, _name, _lang in common_keys:
        common_by_type[resource_type] = common_by_type.get(resource_type, 0) + 1
    return {
        "target": str(target_path),
        "donor": str(donor_path),
        "selected_target_language": target_language,
        "selected_donor_language": donor_language,
        "common_resource_keys": len(common_keys),
        "common_by_type": common_by_type,
        "string_candidates": len(candidates),
        "string_candidates_fit_in_place": sum(
            bool(item["fits_in_place"]) for item in candidates
        ),
        "sample": candidates[:60],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("pe", type=Path)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("target", type=Path)
    compare_parser.add_argument("donor", type=Path)

    args = parser.parse_args()
    if args.command == "summary":
        payload = summarize(args.pe.resolve())
    else:
        payload = compare(args.target.resolve(), args.donor.resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
