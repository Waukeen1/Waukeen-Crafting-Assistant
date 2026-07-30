"""Pure profile and threshold rules for map crafting."""

from __future__ import annotations

import re


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
    match = re.search(r"(?im)^\s*Map Tier:\s*(\d+)\s*$", item_text or "")
    return int(match.group(1)) if match else None


def is_map_item(item_text: str) -> bool:
    return bool(re.search(r"(?im)^\s*Item Class:\s*Maps\s*$", item_text or ""))


def is_corrupted(item_text: str) -> bool:
    return bool(re.search(r"(?im)^\s*Corrupted\s*$", item_text or ""))


def is_unidentified(item_text: str) -> bool:
    return bool(re.search(r"(?im)^\s*Unidentified\s*$", item_text or ""))


def alchemy_vaal_start_failures(item_text: str, required_tier: int = 16) -> list[str]:
    failures = []
    if not is_map_item(item_text):
        failures.append("item map değil")
    tier = parse_map_tier(item_text)
    if tier != required_tier:
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
