"""Parsers and serializers for the Win32 menu and dialog resource formats.

Only display text is edited. Numeric command/control identifiers, styles,
coordinates, creation data, classes, and help identifiers are preserved from
the target uVision build.
"""

from __future__ import annotations

import copy
import struct
from typing import Any


DS_SETFONT = 0x00000040
MF_POPUP = 0x0010
MF_END = 0x0080
MENUEX_POPUP = 0x0001
MENUEX_END = 0x0080


class ResourceFormatError(ValueError):
    pass


def _require(data: bytes, offset: int, size: int) -> None:
    if offset < 0 or offset + size > len(data):
        raise ResourceFormatError(
            f"Resource ended at {len(data)} while reading {size} bytes at {offset}"
        )


def _align(value: int, boundary: int) -> int:
    return (value + boundary - 1) & ~(boundary - 1)


def _pad(buffer: bytearray, boundary: int) -> None:
    while len(buffer) % boundary:
        buffer.append(0)


def _read_u16(data: bytes, offset: int) -> tuple[int, int]:
    _require(data, offset, 2)
    return struct.unpack_from("<H", data, offset)[0], offset + 2


def _read_utf16z(data: bytes, offset: int) -> tuple[str, int]:
    start = offset
    while True:
        value, offset = _read_u16(data, offset)
        if value == 0:
            raw = data[start : offset - 2]
            return raw.decode("utf-16le", errors="strict"), offset


def _write_utf16z(buffer: bytearray, text: str) -> None:
    buffer.extend(text.encode("utf-16le"))
    buffer.extend(b"\x00\x00")


def _read_spec(data: bytes, offset: int) -> tuple[tuple[str, int | str], int]:
    first, next_offset = _read_u16(data, offset)
    if first == 0:
        return ("none", 0), next_offset
    if first == 0xFFFF:
        ordinal, next_offset = _read_u16(data, next_offset)
        return ("ordinal", ordinal), next_offset
    text, next_offset = _read_utf16z(data, offset)
    return ("string", text), next_offset


def _write_spec(buffer: bytearray, value: tuple[str, int | str]) -> None:
    kind, payload = value
    if kind == "none":
        buffer.extend(struct.pack("<H", 0))
    elif kind == "ordinal":
        buffer.extend(struct.pack("<HH", 0xFFFF, int(payload)))
    elif kind == "string":
        _write_utf16z(buffer, str(payload))
    else:
        raise ResourceFormatError(f"Unknown variable field kind: {kind}")


def parse_menu(data: bytes) -> dict[str, Any]:
    _require(data, 0, 4)
    version, offset = struct.unpack_from("<HH", data, 0)
    first_item = 4 + offset
    if first_item > len(data):
        raise ResourceFormatError("Menu header points outside the resource")

    def parse_standard_level(position: int) -> tuple[list[dict[str, Any]], int]:
        items: list[dict[str, Any]] = []
        while True:
            flags, position = _read_u16(data, position)
            is_popup = bool(flags & MF_POPUP)
            item_id = None
            if not is_popup:
                item_id, position = _read_u16(data, position)
            text, position = _read_utf16z(data, position)
            children: list[dict[str, Any]] = []
            if is_popup:
                children, position = parse_standard_level(position)
            items.append(
                {
                    "flags": flags,
                    "id": item_id,
                    "text": text,
                    "children": children,
                }
            )
            if flags & MF_END:
                return items, position

    def parse_extended_level(position: int) -> tuple[list[dict[str, Any]], int]:
        items: list[dict[str, Any]] = []
        while True:
            position = _align(position, 4)
            _require(data, position, 14)
            item_type, state, item_id = struct.unpack_from("<LLL", data, position)
            position += 12
            flags, position = _read_u16(data, position)
            text, position = _read_utf16z(data, position)
            position = _align(position, 4)
            help_id = None
            children: list[dict[str, Any]] = []
            if flags & MENUEX_POPUP:
                _require(data, position, 4)
                help_id = struct.unpack_from("<L", data, position)[0]
                position += 4
                children, position = parse_extended_level(position)
            items.append(
                {
                    "type": item_type,
                    "state": state,
                    "id": item_id,
                    "flags": flags,
                    "help_id": help_id,
                    "text": text,
                    "children": children,
                }
            )
            if flags & MENUEX_END:
                return items, position

    if version == 0:
        items, end = parse_standard_level(first_item)
        kind = "standard"
    elif version == 1:
        items, end = parse_extended_level(first_item)
        kind = "extended"
    else:
        raise ResourceFormatError(f"Unsupported menu template version {version}")
    return {
        "kind": kind,
        "prefix": data[:first_item],
        "items": items,
        "tail": data[end:],
    }


def serialize_menu(menu: dict[str, Any]) -> bytes:
    output = bytearray(menu["prefix"])

    def write_standard(items: list[dict[str, Any]]) -> None:
        for item in items:
            output.extend(struct.pack("<H", item["flags"]))
            if not (item["flags"] & MF_POPUP):
                output.extend(struct.pack("<H", item["id"]))
            _write_utf16z(output, item["text"])
            if item["flags"] & MF_POPUP:
                write_standard(item["children"])

    def write_extended(items: list[dict[str, Any]]) -> None:
        for item in items:
            _pad(output, 4)
            output.extend(
                struct.pack("<LLLH", item["type"], item["state"], item["id"], item["flags"])
            )
            _write_utf16z(output, item["text"])
            _pad(output, 4)
            if item["flags"] & MENUEX_POPUP:
                output.extend(struct.pack("<L", item["help_id"]))
                write_extended(item["children"])

    if menu["kind"] == "standard":
        write_standard(menu["items"])
    else:
        write_extended(menu["items"])
    output.extend(menu["tail"])
    return bytes(output)


def menu_skeleton(menu: dict[str, Any]) -> tuple[Any, ...]:
    def walk(items: list[dict[str, Any]]) -> tuple[Any, ...]:
        result = []
        for item in items:
            if menu["kind"] == "standard":
                meta = (item["flags"], item["id"])
            else:
                meta = (
                    item["type"],
                    item["state"],
                    item["id"],
                    item["flags"],
                    item["help_id"],
                )
            result.append((meta, walk(item["children"])))
        return tuple(result)

    return (menu["kind"], walk(menu["items"]))


def translate_menu(
    target: dict[str, Any], donor: dict[str, Any], is_translation
) -> tuple[dict[str, Any], int]:
    translated = copy.deepcopy(target)
    changed = 0

    def walk(target_items: list[dict[str, Any]], donor_items: list[dict[str, Any]]) -> None:
        nonlocal changed
        for target_item, donor_item in zip(target_items, donor_items):
            if donor_item["text"] and is_translation(donor_item["text"]):
                target_item["text"] = donor_item["text"]
                changed += 1
            walk(target_item["children"], donor_item["children"])

    if menu_skeleton(target) == menu_skeleton(donor):
        walk(translated["items"], donor["items"])
    return translated, changed


def parse_dialog(data: bytes) -> dict[str, Any]:
    _require(data, 0, 4)
    is_extended = struct.unpack_from("<H", data, 2)[0] == 0xFFFF
    position = 0
    if is_extended:
        _require(data, 0, 26)
        fixed = struct.unpack_from("<HHLLLHhhhh", data, 0)
        position = 26
        style = fixed[4]
        item_count = fixed[5]
        kind = "extended"
    else:
        _require(data, 0, 18)
        fixed = struct.unpack_from("<LLHhhhh", data, 0)
        position = 18
        style = fixed[0]
        item_count = fixed[2]
        kind = "standard"

    menu, position = _read_spec(data, position)
    window_class, position = _read_spec(data, position)
    title, position = _read_spec(data, position)
    font = None
    if style & DS_SETFONT:
        if is_extended:
            _require(data, position, 6)
            point_size, weight = struct.unpack_from("<HH", data, position)
            italic = data[position + 4]
            charset = data[position + 5]
            position += 6
            typeface, position = _read_utf16z(data, position)
            font = (point_size, weight, italic, charset, typeface)
        else:
            point_size, position = _read_u16(data, position)
            typeface, position = _read_utf16z(data, position)
            font = (point_size, typeface)

    items: list[dict[str, Any]] = []
    for _ in range(item_count):
        position = _align(position, 4)
        if is_extended:
            _require(data, position, 24)
            item_fixed = struct.unpack_from("<LLLhhhhL", data, position)
            position += 24
            item_id = item_fixed[-1]
        else:
            _require(data, position, 18)
            item_fixed = struct.unpack_from("<LLhhhhH", data, position)
            position += 18
            item_id = item_fixed[-1]
        item_class, position = _read_spec(data, position)
        item_title, position = _read_spec(data, position)
        extra_size, position = _read_u16(data, position)
        if extra_size:
            payload_size = extra_size - 2
            if payload_size < 0:
                raise ResourceFormatError("Invalid dialog creation-data size")
            _require(data, position, payload_size)
            extra_payload = data[position : position + payload_size]
            position += payload_size
        else:
            extra_payload = b""
        items.append(
            {
                "fixed": item_fixed,
                "id": item_id,
                "class": item_class,
                "title": item_title,
                "extra_size": extra_size,
                "extra_payload": extra_payload,
            }
        )
    return {
        "kind": kind,
        "fixed": fixed,
        "menu": menu,
        "class": window_class,
        "title": title,
        "font": font,
        "items": items,
        "tail": data[position:],
    }


def serialize_dialog(dialog: dict[str, Any]) -> bytes:
    output = bytearray()
    if dialog["kind"] == "extended":
        output.extend(struct.pack("<HHLLLHhhhh", *dialog["fixed"]))
    else:
        output.extend(struct.pack("<LLHhhhh", *dialog["fixed"]))
    _write_spec(output, dialog["menu"])
    _write_spec(output, dialog["class"])
    _write_spec(output, dialog["title"])
    if dialog["font"] is not None:
        if dialog["kind"] == "extended":
            point_size, weight, italic, charset, typeface = dialog["font"]
            output.extend(struct.pack("<HHBB", point_size, weight, italic, charset))
            _write_utf16z(output, typeface)
        else:
            point_size, typeface = dialog["font"]
            output.extend(struct.pack("<H", point_size))
            _write_utf16z(output, typeface)
    for item in dialog["items"]:
        _pad(output, 4)
        if dialog["kind"] == "extended":
            output.extend(struct.pack("<LLLhhhhL", *item["fixed"]))
        else:
            output.extend(struct.pack("<LLhhhhH", *item["fixed"]))
        _write_spec(output, item["class"])
        _write_spec(output, item["title"])
        output.extend(struct.pack("<H", item["extra_size"]))
        output.extend(item["extra_payload"])
    output.extend(dialog["tail"])
    return bytes(output)


def dialog_skeleton(dialog: dict[str, Any]) -> tuple[Any, ...]:
    return (
        dialog["kind"],
        tuple((item["id"], item["class"]) for item in dialog["items"]),
    )


def translate_dialog(
    target: dict[str, Any], donor: dict[str, Any], is_translation
) -> tuple[dict[str, Any], int]:
    translated = copy.deepcopy(target)
    changed = 0
    same_structure = dialog_skeleton(target) == dialog_skeleton(donor)

    if donor["title"][0] == "string" and is_translation(str(donor["title"][1])):
        translated["title"] = donor["title"]
        changed += 1

    if same_structure:
        for target_item, donor_item in zip(translated["items"], donor["items"]):
            if donor_item["title"][0] == "string" and is_translation(
                str(donor_item["title"][1])
            ):
                target_item["title"] = donor_item["title"]
                changed += 1
    else:
        donor_by_id: dict[tuple[int, tuple[str, int | str]], list[dict[str, Any]]] = {}
        target_by_id: dict[tuple[int, tuple[str, int | str]], list[dict[str, Any]]] = {}
        for item in donor["items"]:
            donor_by_id.setdefault((item["id"], item["class"]), []).append(item)
        for item in translated["items"]:
            target_by_id.setdefault((item["id"], item["class"]), []).append(item)
        for key in donor_by_id.keys() & target_by_id.keys():
            if len(donor_by_id[key]) != 1 or len(target_by_id[key]) != 1:
                continue
            donor_item = donor_by_id[key][0]
            target_item = target_by_id[key][0]
            if donor_item["title"][0] == "string" and is_translation(
                str(donor_item["title"][1])
            ):
                target_item["title"] = donor_item["title"]
                changed += 1
    return translated, changed
