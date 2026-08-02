"""Pure profile and threshold rules for map crafting."""

from __future__ import annotations

import json
import re
from pathlib import Path


PROFILE_NORMAL = "normal"
PROFILE_MEMORY_NIGHTMARE = "memory_nightmare"
PROFILE_LABELS = {
    PROFILE_NORMAL: "Normal Map",
    PROFILE_MEMORY_NIGHTMARE: "Memory / Nightmare",
}

THRESHOLD_SPECS = (
    ("Quantity", "map_quantity_thresh", "quantity"),
    ("Rarity", "map_rarity_thresh", "rarity"),
    ("Pack size", "map_pack_size_thresh", "pack_size"),
)


def load_affix_groups(path) -> list[dict]:
    source = Path(path)
    if not source.exists():
        return []
    raw = json.loads(source.read_text(encoding="utf-8-sig"))
    groups = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        mods = [
            mod.strip()
            for mod in entry.get("mods", [])
            if isinstance(mod, str) and mod.strip()
        ]
        if not mods:
            continue
        groups.append({
            "tier": entry.get("tier", ""),
            "affix_type": entry.get("affix_type", ""),
            "mods": mods,
            "quantity": int(entry.get("quantity", 0) or 0),
            "rarity": int(entry.get("rarity", 0) or 0),
            "pack": int(entry.get("pack", 0) or 0),
            "currency": int(entry.get("currency", 0) or 0),
            "scarab": int(entry.get("scarab", 0) or 0),
            "divination": int(entry.get("divination", 0) or 0),
            "maps": int(entry.get("maps", 0) or 0),
        })
    return groups


def unique_affixes(groups: list[dict]) -> list[str]:
    seen = set()
    affixes = []
    for group in groups:
        for mod in group.get("mods", []):
            if mod not in seen:
                seen.add(mod)
                affixes.append(mod)
    return affixes


def normalize_profile(value) -> str:
    normalized = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized in {
        PROFILE_MEMORY_NIGHTMARE,
        "memory",
        "nightmare",
        "memory/nightmare",
        "memory_/_nightmare",
    }:
        return PROFILE_MEMORY_NIGHTMARE
    return PROFILE_NORMAL


def profile_label(value) -> str:
    return PROFILE_LABELS[normalize_profile(value)]


def active_forbidden(settings: dict) -> list[str]:
    profile = normalize_profile(settings.get("map_profile"))
    if profile == PROFILE_MEMORY_NIGHTMARE:
        return list(settings.get("map_memory_forbidden") or [])
    return list(
        settings.get("map_normal_forbidden")
        or settings.get("map_forbidden")
        or []
    )


def threshold_checks(summary_stats: dict, settings: dict) -> list[tuple[str, object, object]]:
    return [
        (label, settings.get(setting_key), summary_stats.get(stat_key))
        for label, setting_key, stat_key in THRESHOLD_SPECS
    ]


def threshold_failures(summary_stats: dict, settings: dict) -> list[str]:
    failures = []
    for label, threshold, actual in threshold_checks(summary_stats, settings):
        if threshold in (None, ""):
            continue
        threshold_value = int(threshold)
        actual_value = 0 if actual is None else int(actual)
        if actual_value < threshold_value:
            failures.append(f"{label}={actual_value}/{threshold_value}")
    return failures


def evaluate(forbidden_match_count: int, summary_stats: dict, settings: dict) -> dict:
    failures = threshold_failures(summary_stats, settings)
    forbidden_count = max(0, int(forbidden_match_count or 0))
    profile = normalize_profile(settings.get("map_profile"))
    return {
        "profile": profile,
        "profile_label": PROFILE_LABELS[profile],
        "forbidden_count": forbidden_count,
        "threshold_failures": failures,
        "accepted": forbidden_count == 0 and not failures,
    }


def parse_map_tier(item_text: str) -> int | None:
    match = re.search(
        r"(?im)^\s*(?:Map\s+)?Tier\s*:\s*(\d+)\b",
        item_text or "",
    )
    return int(match.group(1)) if match else None


def is_map_item(item_text: str) -> bool:
    return bool(re.search(r"(?im)^\s*Item Class:\s*Maps\s*$", item_text or ""))


def is_corrupted(item_text: str) -> bool:
    return bool(re.search(r"(?im)^\s*Corrupted\s*$", item_text or ""))


def is_unidentified(item_text: str) -> bool:
    return bool(re.search(r"(?im)^\s*Unidentified\s*$", item_text or ""))


def alchemy_vaal_start_failures(
    item_text: str,
    required_tier: int = 16,
    allow_missing_tier: bool = False,
) -> list[str]:
    failures = []
    if not is_map_item(item_text):
        failures.append("item map değil")
    tier = parse_map_tier(item_text)
    if tier is None and not allow_missing_tier:
        failures.append(f"Map Tier=? (hedef {required_tier})")
    elif tier is not None and tier != required_tier:
        failures.append(f"Map Tier={tier if tier is not None else '?'} (hedef {required_tier})")
    rarity_match = re.search(r"(?im)^\s*Rarity:\s*(\w+)\s*$", item_text or "")
    rarity = rarity_match.group(1).casefold() if rarity_match else ""
    if rarity not in {"normal", "rare"}:
        failures.append(f"Rarity={rarity or '?'} (Normal veya Rare gerekli)")
    if is_corrupted(item_text):
        failures.append("item zaten Corrupted")
    return failures


def alchemy_vaal_final_failures(
    item_text: str,
    forbidden_match_count: int,
    summary_stats: dict,
    settings: dict,
) -> list[str]:
    failures = []
    if not is_map_item(item_text):
        failures.append("sonuç map değil")
    if not is_corrupted(item_text):
        failures.append("Vaal uygulanmamış")
    if is_unidentified(item_text):
        failures.append("Unidentified: modlar doğrulanamıyor")
    evaluation = evaluate(forbidden_match_count, summary_stats, settings)
    if evaluation["forbidden_count"]:
        failures.append(f"{evaluation['forbidden_count']} istenmeyen mod")
    failures.extend(evaluation["threshold_failures"])
    return failures
