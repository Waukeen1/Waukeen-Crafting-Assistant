"""Pure catalog, matching, and decision helpers for generic item crafting."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re


INFLUENCE_ITEM_LINES = {
    "Shaper": "shaper item",
    "Elder": "elder item",
    "Warlord": "warlord item",
    "Hunter": "hunter item",
    "Crusader": "crusader item",
    "Redeemer": "redeemer item",
}
ITEM_LEVEL_RE = re.compile(r"^item level:\s*(\d+)\s*$", re.I)
RARITY_RE = re.compile(r"^rarity:\s*(.+?)\s*$", re.I)
ADVANCED_ROLL_RANGE_RE = re.compile(
    r"(?<=\d)\([+-]?\d+(?:\.\d+)?(?:-[+-]?\d+(?:\.\d+)?)?\)"
)
DISPLAY_ANNOTATION_RE = re.compile(r"\s+\((?:crafted|fractured)\)\s*$", re.I)
NON_EXPLICIT_BLOCK_MARKERS = (
    "(enchant)",
    "enchantment modifier",
    "(implicit)",
    "implicit modifier",
    "requirements:",
    "item level:",
    "sockets:",
    "place into",
)


def load_catalog(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as source:
        catalog = json.load(source)
    if catalog.get("schema") != 1:
        raise ValueError("Unsupported item-affix catalog schema.")
    catalog["base_by_name"] = {base["name"].casefold(): base for base in catalog["bases"]}
    catalog["mod_by_id"] = {mod["id"]: mod for mod in catalog["mods"]}
    return catalog


def base_names(catalog: dict) -> list[str]:
    return sorted((base["name"] for base in catalog["bases"]), key=str.casefold)


def matching_base_names(
    catalog: dict,
    query: str,
    minimum_chars: int = 3,
) -> list[str]:
    normalized = (query or "").strip().casefold()
    if len(normalized) < minimum_chars:
        return []
    return [
        name
        for name in base_names(catalog)
        if normalized in name.casefold()
    ]


def find_base(catalog: dict, name: str) -> dict | None:
    return catalog["base_by_name"].get((name or "").strip().casefold())


def spawn_weight(mod: dict, effective_tags: set[str]) -> int:
    for row in mod.get("weights", []):
        if row.get("tag") in effective_tags:
            return int(row.get("weight", 0))
    return 0


def eligible_mods(catalog: dict, base_name: str, influence: str, item_level: int) -> list[dict]:
    base = find_base(catalog, base_name)
    if not base:
        return []
    effective_tags = set(base.get("tags", []))
    if influence and influence != "None":
        influence_tag = base.get("influences", {}).get(influence)
        if not influence_tag:
            return []
        effective_tags.add(influence_tag)
    flask_base = "flask" in effective_tags

    result = []
    for mod in catalog["mods"]:
        flask_mod = mod.get("domain") == "flask"
        if flask_base != flask_mod:
            continue
        if int(mod.get("level", 1)) > int(item_level):
            continue
        weight = spawn_weight(mod, effective_tags)
        if weight <= 0:
            continue
        copy = dict(mod)
        copy["spawn_weight"] = weight
        result.append(copy)
    result.sort(
        key=lambda mod: (
            0 if mod["type"] == "prefix" else 1,
            " / ".join(line["text"] for line in mod["lines"]).casefold(),
            -int(mod.get("level", 1)),
        )
    )
    return result


@lru_cache(maxsize=16_384)
def _compiled(pattern: str):
    return re.compile(pattern, re.I)


def _line_matches(line_spec: dict, actual: str) -> bool:
    actual = DISPLAY_ANNOTATION_RE.sub("", (actual or "").strip())
    match = _compiled(line_spec["pattern"]).fullmatch(actual)
    if not match:
        return False
    values = [float(value) for value in match.groups()]
    ranges = line_spec.get("ranges", [])
    if len(values) != len(ranges):
        return False
    return all(float(low) <= value <= float(high) for value, (low, high) in zip(values, ranges))


def _match_line_indices(mod: dict, actual_mods: list[str], available: set[int] | None = None):
    available_indices = set(range(len(actual_mods))) if available is None else set(available)
    line_specs = mod.get("lines", [])

    def search(spec_index: int, chosen: list[int]):
        if spec_index >= len(line_specs):
            return chosen
        spec = line_specs[spec_index]
        for index in sorted(available_indices - set(chosen)):
            if _line_matches(spec, actual_mods[index]):
                result = search(spec_index + 1, chosen + [index])
                if result is not None:
                    return result
        return None

    return search(0, [])


def mod_matches(mod: dict, actual_mods: list[str]) -> bool:
    return _match_line_indices(mod, actual_mods) is not None


def item_identity(item_text: str) -> dict:
    lines = [line.strip() for line in (item_text or "").splitlines() if line.strip()]
    header_lines = []
    rarity_index = next(
        (index for index, line in enumerate(lines) if line.casefold().startswith("rarity:")),
        None,
    )
    if rarity_index is not None:
        for line in lines[rarity_index + 1 :]:
            if line == "--------":
                break
            header_lines.append(line)
    item_level = None
    rarity = "Unknown"
    for line in lines:
        rarity_match = RARITY_RE.match(line)
        if rarity_match:
            rarity = rarity_match.group(1).strip().capitalize()
        match = ITEM_LEVEL_RE.match(line)
        if match:
            item_level = int(match.group(1))
    return {
        "lines": lines,
        "line_set": {line.casefold() for line in lines},
        "header_lines": header_lines,
        "item_level": item_level,
        "rarity": rarity,
        "corrupted": any(line.casefold() == "corrupted" for line in lines),
        "mirrored": any(line.casefold() == "mirrored" for line in lines),
    }


def _header_contains_base(header_lines: list[str], base_name: str) -> bool:
    base_pattern = re.compile(
        rf"(?<!\w){re.escape((base_name or '').strip())}(?!\w)",
        re.I,
    )
    return any(base_pattern.search(line) for line in header_lines)


def validate_item(item_text: str, base_name: str, influence: str) -> tuple[bool, str, int | None]:
    identity = item_identity(item_text)
    if not _header_contains_base(identity["header_lines"], base_name):
        return False, f"Cursor altindaki base '{base_name}' degil.", identity["item_level"]
    if influence and influence != "None":
        required_line = INFLUENCE_ITEM_LINES.get(influence)
        if required_line and required_line not in identity["line_set"]:
            return False, f"Item {influence} influence tasimiyor.", identity["item_level"]
    if identity["corrupted"] or identity["mirrored"]:
        return False, "Corrupted veya mirrored item craft edilemez.", identity["item_level"]
    if identity["item_level"] is None:
        return False, "Item Level okunamadi.", None
    return True, "", identity["item_level"]


def _catalog_records(eligible: list[dict], actual_mods: list[str]) -> list[dict]:
    available = set(range(len(actual_mods)))
    records = []
    seen_groups = set()
    ordered = sorted(
        eligible,
        key=lambda mod: (len(mod.get("lines", [])), int(mod.get("level", 1))),
        reverse=True,
    )
    for mod in ordered:
        group_key = (mod.get("type"), mod.get("group"))
        if group_key in seen_groups:
            continue
        indices = _match_line_indices(mod, actual_mods, available)
        if indices is None:
            continue
        seen_groups.add(group_key)
        available.difference_update(indices)
        records.append(
            {
                "id": mod["id"],
                "type": mod["type"],
                "group": mod.get("group", ""),
                "indices": indices,
                "mods": [actual_mods[index] for index in indices],
            }
        )
    for index in sorted(available):
        records.append(
            {
                "id": f"unknown:{index}",
                "type": "unknown",
                "group": "",
                "indices": [index],
                "mods": [actual_mods[index]],
            }
        )
    return records


def _separator_blocks(item_text: str) -> list[list[str]]:
    blocks = []
    current = []
    after_separator = False
    for raw in (item_text or "").splitlines():
        line = raw.strip()
        if line == "--------":
            if after_separator and current:
                blocks.append(current)
            current = []
            after_separator = True
            continue
        if after_separator and line:
            current.append(line)
    if after_separator and current:
        blocks.append(current)
    return blocks


def _clean_explicit_candidate(block: list[str]) -> list[str]:
    cleaned = []
    for raw in block:
        line = raw.strip()
        if not line or line.startswith("{"):
            continue
        if line.startswith("(") and line.endswith(")"):
            continue
        line = ADVANCED_ROLL_RANGE_RE.sub("", line)
        if line:
            cleaned.append(line)
    return cleaned


def extract_explicit_mods(
    catalog: dict,
    base_name: str,
    influence: str,
    item_level: int,
    item_text: str,
) -> list[str]:
    """Select the explicit affix block by matching it against the real mod pool."""
    eligible = eligible_mods(catalog, base_name, influence, item_level)
    best_block = []
    best_score = (0, 0)

    for raw_block in _separator_blocks(item_text):
        lowered = [line.casefold() for line in raw_block]
        if any(
            marker in line
            for line in lowered
            for marker in NON_EXPLICIT_BLOCK_MARKERS
        ):
            continue

        block = _clean_explicit_candidate(raw_block)
        if not block:
            continue
        records = _catalog_records(eligible, block)
        known_records = [
            record for record in records if record["type"] in {"prefix", "suffix"}
        ]
        known_lines = sum(len(record["indices"]) for record in known_records)
        score = (len(known_records), known_lines)
        if score > best_score:
            best_score = score
            best_block = block

    return best_block


def parse_item_for_craft(
    catalog: dict,
    base_name: str,
    influence: str,
    item_text: str,
) -> tuple[str, list[str], int | None]:
    identity = item_identity(item_text)
    item_level = identity["item_level"]
    if item_level is None:
        return identity["rarity"], [], None
    return (
        identity["rarity"],
        extract_explicit_mods(
            catalog,
            base_name,
            influence,
            item_level,
            item_text,
        ),
        item_level,
    )


def analyze(catalog: dict, base_name: str, influence: str, item_level: int, actual_mods: list[str], target_ids: list[str], required_count: int) -> dict:
    eligible = eligible_mods(catalog, base_name, influence, item_level)
    eligible_by_id = {mod["id"]: mod for mod in eligible}
    targets = [eligible_by_id[target_id] for target_id in target_ids if target_id in eligible_by_id]
    matched_targets = [target for target in targets if mod_matches(target, actual_mods)]
    matched_ids = {target["id"] for target in matched_targets}
    records = _catalog_records(eligible, actual_mods)
    prefix_count = sum(record["type"] == "prefix" for record in records)
    suffix_count = sum(record["type"] == "suffix" for record in records)
    unknown_count = sum(record["type"] == "unknown" for record in records)
    target_groups = {(target["type"], target.get("group")) for target in matched_targets}
    junk_records = [
        record
        for record in records
        if (record["type"], record.get("group")) not in target_groups
    ]
    missing_targets = [target for target in targets if target["id"] not in matched_ids]
    required = max(1, min(int(required_count), len(targets))) if targets else 1
    return {
        "eligible": eligible,
        "targets": targets,
        "records": records,
        "matched_target_ids": sorted(matched_ids),
        "matched_count": len(matched_ids),
        "required_count": required,
        "goal_met": len(matched_ids) >= required,
        "missing_targets": missing_targets,
        "prefix_count": prefix_count,
        "suffix_count": suffix_count,
        "unknown_count": unknown_count,
        "affix_count": len(records),
        "junk_records": junk_records,
    }


def _missing_type_has_space(summary: dict, rarity: str) -> bool:
    limit = 1 if rarity.casefold() == "magic" else 3
    for target in summary["missing_targets"]:
        if target["type"] == "prefix" and summary["prefix_count"] < limit:
            return True
        if target["type"] == "suffix" and summary["suffix_count"] < limit:
            return True
    return False


def choose_chance_to_unique_action(rarity: str) -> tuple[str, str]:
    """Return the next safe action for a Chance + Scour unique loop."""
    rarity_low = (rarity or "").strip().casefold()
    if rarity_low == "unique":
        return "done", "Unique item bulundu."
    if rarity_low == "normal":
        return "chance", "Normal item -> Orb of Chance."
    if rarity_low in {"magic", "rare"}:
        return "scour", f"{rarity} sonuc -> Orb of Scouring ile normale donulecek."
    return "stop", f"Desteklenmeyen veya okunamayan rarity: {rarity}"


def choose_action(rarity: str, summary: dict, settings: dict) -> tuple[str, str]:
    rarity_low = (rarity or "").casefold()
    affix_limit = 2 if rarity_low == "magic" else (6 if rarity_low == "rare" else None)
    if affix_limit is not None and summary["affix_count"] > affix_limit:
        return (
            "stop",
            f"Parser guvenlik hatasi: {rarity} itemde "
            f"{summary['affix_count']} affix okundu; tiklama yapilmadi.",
        )
    if summary["goal_met"]:
        return "done", "Hedef tamamlandi."
    if rarity_low == "normal":
        return "transmute", "Normal item magic yapilacak."
    if rarity_low == "magic":
        if (
            settings.get("item_use_augment", True)
            and summary["affix_count"] < 2
            and _missing_type_has_space(summary, "magic")
        ):
            return "augment", "Bos uygun affix slotu hedefi getirebilir."
        if (
            settings.get("item_use_regal", False)
            and summary["matched_count"] > 0
            and _missing_type_has_space(summary, "rare")
        ):
            return "regal", "Mevcut hedef korunup eksik hedef Regal ile aranacak."
        return "alter", "Magic item hedefe ulasamiyor; yeni Alteration rollu."
    if rarity_low == "rare":
        if (
            settings.get("item_use_exalt", False)
            and summary["matched_count"] > 0
            and summary["affix_count"] < 6
            and _missing_type_has_space(summary, "rare")
        ):
            return "exalt", "Bos affix slotunda eksik hedef Exalted ile aranacak."
        if (
            settings.get("item_use_annul", False)
            and summary["matched_count"] > 0
            and summary["junk_records"]
        ):
            return "annul", "Hedef korunarak junk affix silinmeye calisilacak."
        return "scour", "Rare itemde hedef tamamlanamadi; yeniden magic akisa donulecek."
    return "stop", f"Desteklenmeyen rarity: {rarity}"
