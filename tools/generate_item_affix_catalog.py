#!/usr/bin/env python3
"""Generate a compact, filterable item-affix catalog from Path of Building data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re


MOD_ENTRY_RE = re.compile(
    r'^\s*\["(?P<id>(?:\\.|[^"\\])*)"\]\s*=\s*\{(?P<body>.*)\},\s*$'
)
TYPE_RE = re.compile(r'\btype\s*=\s*"(Prefix|Suffix)"')
AFFIX_RE = re.compile(r'\baffix\s*=\s*"((?:\\.|[^"\\])*)"')
LEVEL_RE = re.compile(r'\blevel\s*=\s*(\d+)')
GROUP_RE = re.compile(r'\bgroup\s*=\s*"((?:\\.|[^"\\])*)"')
BASE_START_RE = re.compile(r'^itemBases\["((?:\\.|[^"\\])*)"\]\s*=\s*\{\s*$')
BASE_TYPE_RE = re.compile(r'^\s*type\s*=\s*"((?:\\.|[^"\\])*)",?\s*$')
BASE_SUBTYPE_RE = re.compile(r'^\s*subType\s*=\s*"((?:\\.|[^"\\])*)",?\s*$')
QUOTED_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
NUMBER_RE = re.compile(
    r"\((?P<range_min>[+-]?\d+(?:\.\d+)?)-(?P<range_max>[+-]?\d+(?:\.\d+)?)\)"
    r"|(?P<single>[+-]?\d+(?:\.\d+)?)"
)

INFLUENCE_NAMES = {
    "shaper": "Shaper",
    "elder": "Elder",
    "adjudicator": "Warlord",
    "basilisk": "Hunter",
    "crusader": "Crusader",
    "eyrie": "Redeemer",
}


def _lua_string(value: str) -> str:
    return json.loads(f'"{value}"')


def _quoted_values(value: str) -> list[str]:
    return [_lua_string(match.group(1)) for match in QUOTED_RE.finditer(value)]


def _list_field(body: str, name: str) -> list[str]:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*\{{(?P<value>.*?)\}}", body)
    return _quoted_values(match.group("value")) if match else []


def _number_list_field(body: str, name: str) -> list[int]:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*\{{(?P<value>.*?)\}}", body)
    if not match:
        return []
    return [int(value) for value in re.findall(r"-?\d+", match.group("value"))]


def _pattern_and_ranges(text: str) -> tuple[str, list[list[float]]]:
    parts: list[str] = []
    ranges: list[list[float]] = []
    cursor = 0
    for match in NUMBER_RE.finditer(text):
        parts.append(re.escape(text[cursor : match.start()]))
        parts.append(r"([+-]?\d+(?:\.\d+)?)")
        if match.group("single") is not None:
            value = float(match.group("single"))
            ranges.append([value, value])
        else:
            low = float(match.group("range_min"))
            high = float(match.group("range_max"))
            ranges.append([min(low, high), max(low, high)])
        cursor = match.end()
    parts.append(re.escape(text[cursor:]))
    return "^" + "".join(parts) + "$", ranges


def parse_mods(path: Path, domain: str = "") -> list[dict]:
    entries: list[dict] = []
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        match = MOD_ENTRY_RE.match(raw_line)
        if not match:
            continue
        body = match.group("body")
        type_match = TYPE_RE.search(body)
        affix_match = AFFIX_RE.search(body)
        stat_order_pos = body.find("statOrder")
        if not type_match or not affix_match or stat_order_pos < 0:
            continue

        text_segment = body[affix_match.end() : stat_order_pos]
        lines = _quoted_values(text_segment)
        weight_keys = _list_field(body, "weightKey")
        weight_values = _number_list_field(body, "weightVal")
        weights = [
            {"tag": tag, "weight": weight_values[index] if index < len(weight_values) else 0}
            for index, tag in enumerate(weight_keys)
        ]
        if not lines or not any(weight["weight"] > 0 for weight in weights):
            continue

        line_patterns = []
        for text in lines:
            pattern, ranges = _pattern_and_ranges(text)
            line_patterns.append({"text": text, "pattern": pattern, "ranges": ranges})

        level_match = LEVEL_RE.search(body)
        group_match = GROUP_RE.search(body)
        entry = {
            "id": _lua_string(match.group("id")),
            "type": type_match.group(1).lower(),
            "affix": _lua_string(affix_match.group(1)),
            "group": _lua_string(group_match.group(1)) if group_match else "",
            "level": int(level_match.group(1)) if level_match else 1,
            "lines": line_patterns,
            "weights": weights,
            "tags": _list_field(body, "modTags"),
        }
        if domain:
            entry["domain"] = domain
        entries.append(entry)
    return entries


def _parse_inline_map(line: str) -> dict[str, str]:
    result = {}
    for key, value in re.findall(r'(\w+)\s*=\s*"((?:\\.|[^"\\])*)"', line):
        result[key] = _lua_string(value)
    return result


def _parse_inline_keys(line: str) -> list[str]:
    body_match = re.search(r"\{(?P<body>.*)\}", line)
    if not body_match:
        return []
    return sorted(set(re.findall(r"(\w+)\s*=\s*true", body_match.group("body"))))


def parse_bases(directory: Path) -> list[dict]:
    bases: list[dict] = []
    for path in sorted(directory.glob("*.lua")):
        current = None
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            start_match = BASE_START_RE.match(raw_line)
            if start_match:
                current = {
                    "name": _lua_string(start_match.group(1)),
                    "type": "",
                    "subtype": "",
                    "tags": [],
                    "influences": {},
                }
                continue
            if current is None:
                continue
            if raw_line == "}":
                if current["type"] and current["tags"]:
                    current["influences"] = {
                        INFLUENCE_NAMES[key]: value
                        for key, value in current["influences"].items()
                        if key in INFLUENCE_NAMES
                    }
                    bases.append(current)
                current = None
                continue
            type_match = BASE_TYPE_RE.match(raw_line)
            if type_match:
                current["type"] = _lua_string(type_match.group(1))
                continue
            subtype_match = BASE_SUBTYPE_RE.match(raw_line)
            if subtype_match:
                current["subtype"] = _lua_string(subtype_match.group(1))
                continue
            stripped = raw_line.strip()
            if stripped.startswith("tags ="):
                current["tags"] = _parse_inline_keys(stripped)
            elif stripped.startswith("influenceTags ="):
                current["influences"] = _parse_inline_map(stripped)
    return bases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pob-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pob-version", default="")
    args = parser.parse_args()

    mod_path = args.pob_dir / "Data" / "ModExplicit.lua"
    flask_mod_path = args.pob_dir / "Data" / "ModFlask.lua"
    bases_dir = args.pob_dir / "Data" / "Bases"
    if (
        not mod_path.is_file()
        or not flask_mod_path.is_file()
        or not bases_dir.is_dir()
    ):
        raise SystemExit("Path of Building Data directory is incomplete.")

    mods = parse_mods(mod_path)
    mods.extend(parse_mods(flask_mod_path, domain="flask"))
    payload = {
        "schema": 1,
        "source": {
            "name": "Path of Building Community",
            "version": args.pob_version,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "bases": parse_bases(bases_dir),
        "mods": mods,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(payload['bases'])} bases and {len(payload['mods'])} mods "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
