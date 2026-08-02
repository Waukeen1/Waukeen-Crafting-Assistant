import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = ROOT / "data" / "medium_cluster_notable_pools.json"
TEMPLATE_DIR = ROOT / "itemcraft"

DISPLAY_NAMES = {
    "12 % increased Burning Damage": "Burning Damage",
    "12 % increased Chaos Damage over Time": "Chaos DoT",
    "12 % increased Physical Damage over Time": "Physical DoT",
    "12 % increased Cold Damage over Time": "Cold DoT",
    "10 % increased Damage over Time": "Damage over Time",
    "10 % increased Effect of Non-Damaging Ailments(Ailments that do not deal Damage are Scorched, Chilled, Frozen, Brittle, Shocked, and Sapped)": "Non-Damaging Ailments",
    "3 % increased effect of Non-Curse Auras from your Skills": "Aura Effect",
    "2 % increased Effect of your Curses": "Curse Effect",
    "10 % increased Damage while affected by a Herald": "Herald Damage",
    "Minions deal 10 % increased Damage while you are affected by a Herald": "Herald Minion Damage",
    "Exerted Attacks deal 20 % increased Damage": "Exerted Attacks",
    "15 % increased Critical Strike Chance": "Critical Strike Chance",
    "Minions have 12 % increased maximum Life": "Minion Life",
    "10 % increased Area Damage": "Area Damage",
    "10 % increased Projectile Damage": "Projectile Damage",
    "12 % increased Trap Damage12 % increased Mine Damage": "Trap and Mine Damage",
    "12 % increased Totem Damage": "Totem Damage",
    "12 % increased Brand Damage(Brand Damage is any Damage dealt by Brand Skills or by Skills Triggered by a Brand)": "Brand Damage",
    "Channelling Skills deal 12 % increased Damage": "Channelling Damage",
    "6 % increased Flask Effect Duration": "Flask Duration",
    "10 % increased Life Recovery from Flasks10 % increased Mana Recovery from Flasks": "Flask Recovery",
}


def skeleton(base, minimum_item_level):
    return {
        "app_mode": "cluster",
        "craft_logic": "Rare (regal)",
        "augment_mode": "Always use",
        "use_exalt": True,
        "use_annul": False,
        "chain_craft": False,
        "chain_count": 1,
        "cluster_meta": {
            "base": base,
            "passive_count": 5,
            "minimum_item_level": minimum_item_level,
            "source": "PoEDB + official trade API",
            "minimum_chaos": 40,
        },
        "comb_craft_data": {},
        "combo_prices": {},
        "stop_on_two_match": [],
        "annul_combs": [],
        "no_annul_combs": [],
        "solo_regal_mods": [],
        "no_regal_mods": [],
    }


def main():
    payload = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    pools = payload.get("pools", payload)
    created = []
    existing = []
    for pool in pools.values():
        base = pool["clusterName"]
        display = DISPLAY_NAMES[base]
        minimum_item_level = max(int(item.get("level", 1)) for item in pool["notables"])
        path = TEMPLATE_DIR / f"M5 - {display} - ilvl{minimum_item_level} - 40c+.json"
        if path.exists():
            existing.append(path.name)
            continue
        path.write_text(
            json.dumps(skeleton(base, minimum_item_level), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        created.append(path.name)
    print(f"Created: {len(created)}")
    for name in created:
        print(f"  + {name}")
    print(f"Existing: {len(existing)}")


if __name__ == "__main__":
    main()
