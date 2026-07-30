"""Static, offline flask crafting recommendations for the Item Craft UI."""

from __future__ import annotations


UTILITY_PREFIX = {
    "affix": "Alchemist's",
    "text": "(23-27)% reduced Duration / 25% increased effect",
    "level": 80,
}

UTILITY_SUFFIXES = {
    "movement": {
        "affix": "of the Cheetah",
        "text": "(12-14)% increased Movement Speed during Effect",
        "level": 85,
        "why": "En genel ve kolay satilan hiz secenegi.",
    },
    "armour": {
        "affix": "of the Armadillo",
        "text": "(56-60)% increased Armour during Effect",
        "level": 84,
        "why": "Armour tabanli savunma kurulumlarinda en guclu genel suffixlerden.",
    },
    "evasion": {
        "affix": "of the Impala",
        "text": "(56-60)% increased Evasion Rating during Effect",
        "level": 84,
        "why": "Evasion tabanli kurulumlarda yuksek savunma ve iyi pazar talebi saglar.",
    },
    "curse": {
        "affix": "of the Owl",
        "text": "(60-65)% reduced Effect of Curses on you during Effect",
        "level": 84,
        "why": "Mageblood ile curse etkisini cok yuksek oranda bastiran premium savunma secenegi.",
    },
    "resistance": {
        "affix": "of the Rainbow",
        "text": "(18-20)% additional Elemental Resistances during Effect",
        "level": 81,
        "why": "Elemental direncleri rahatlatir ve gear uzerinde suffix alani acar.",
    },
    "critical": {
        "affix": "of Incision",
        "text": "(50-55)% increased Critical Strike Chance during Effect",
        "level": 82,
        "why": "Crit buildleri icin dogrudan hasar ve crit cap destegi verir.",
    },
    "stun": {
        "affix": "of Tenaciousness",
        "text": "(51-55)% Chance to Avoid being Stunned during Effect",
        "level": 80,
        "why": "Yuksek flask effect ile tek flasktan tam stun avoidance saglayabilir.",
    },
    "shock": {
        "affix": "of Bog Moss",
        "text": "(51-55)% chance to Avoid being Shocked during Effect",
        "level": 82,
        "why": "Yuksek flask effect ile tam shock avoidance icin kullanilir.",
    },
    "freeze": {
        "affix": "of the Seal",
        "text": "(51-55)% chance to Avoid being Chilled and Frozen during Effect",
        "level": 80,
        "why": "Yuksek flask effect ile chill ve freeze sorununu tek slotta cozer.",
    },
    "ignite": {
        "affix": "of the Sunfish",
        "text": "(51-55)% chance to Avoid being Ignited during Effect",
        "level": 82,
        "why": "Yuksek flask effect ile tam ignite avoidance icin kullanilir.",
    },
    "spell_leech": {
        "affix": "of Draining",
        "text": "0.8% of Spell Damage Leeched as Energy Shield during Effect",
        "level": 80,
        "why": "Spell ve Energy Shield buildleri icin nis ama degerli sustain secenegi.",
    },
    "attack_leech": {
        "affix": "of Bloodletting",
        "text": "0.8% of Attack Damage Leeched as Life during Effect",
        "level": 80,
        "why": "Attack buildleri icin nis sustain secenegi.",
    },
}

UTILITY_FLASKS = {
    "Topaz Flask": {
        "overview": "Lightning mitigation tabani. Mageblood ve genel savunma pazari icin guclu.",
        "suffixes": ("curse", "resistance", "armour", "evasion", "movement"),
    },
    "Ruby Flask": {
        "overview": "Fire mitigation tabani. Savunma ve elemental direnclerle iyi eslesir.",
        "suffixes": ("resistance", "evasion", "curse", "stun", "movement"),
    },
    "Sapphire Flask": {
        "overview": "Cold mitigation tabani. Hiz, crit ve ailment kurulumlarinda talep gorur.",
        "suffixes": ("movement", "critical", "evasion", "freeze", "curse"),
    },
    "Granite Flask": {
        "overview": "Armour buildlerinin temel utility flaski.",
        "suffixes": ("armour", "curse", "movement", "stun", "resistance"),
    },
    "Basalt Flask": {
        "overview": "Fiziksel savunma odakli buildler icin premium taban.",
        "suffixes": ("armour", "curse", "stun", "movement", "resistance"),
    },
    "Jade Flask": {
        "overview": "Evasion buildlerinin temel utility flaski.",
        "suffixes": ("evasion", "movement", "curse", "resistance", "shock"),
    },
    "Stibnite Flask": {
        "overview": "Evasion ve blind odakli savunma tabani.",
        "suffixes": ("evasion", "movement", "curse", "resistance", "shock"),
    },
    "Quicksilver Flask": {
        "overview": "En likit utility flask tabanlarindan; hareket hizi en onemli kombinasyondur.",
        "suffixes": ("movement", "curse", "resistance", "stun", "critical"),
    },
    "Diamond Flask": {
        "overview": "Crit buildleri icin dogrudan hasar odakli taban.",
        "suffixes": ("critical", "movement", "curse", "resistance", "evasion"),
    },
    "Bismuth Flask": {
        "overview": "Direnc rahatlatan genel amacli taban.",
        "suffixes": ("resistance", "curse", "movement", "stun", "evasion"),
    },
    "Quartz Flask": {
        "overview": "Phasing ve suppression tabani; hizli buildlerde genis kullanim alani var.",
        "suffixes": ("movement", "resistance", "curse", "evasion", "shock"),
    },
    "Silver Flask": {
        "overview": "Onslaught tabani; hiz ve crit secenekleri daha kolay satilir.",
        "suffixes": ("movement", "critical", "curse", "resistance", "evasion"),
    },
    "Sulphur Flask": {
        "overview": "Genel hasar tabani; crit ve hareket hizi en esnek eslesmelerdir.",
        "suffixes": ("critical", "movement", "curse", "resistance", "spell_leech"),
    },
    "Amethyst Flask": {
        "overview": "Chaos direnci tabani; curse azaltma ve sustain ile iyi eslesir.",
        "suffixes": ("curse", "resistance", "movement", "spell_leech", "stun"),
    },
    "Corundum Flask": {
        "overview": "Stun savunmasi tabani; avoidance eslesmesi en belirgin deger secenegidir.",
        "suffixes": ("stun", "curse", "movement", "resistance", "armour"),
    },
    "Gold Flask": {
        "overview": "Magic find tabani; hiz ve direncler en genis alici kitlesine sahiptir.",
        "suffixes": ("movement", "resistance", "curse", "evasion", "armour"),
    },
    "Aquamarine Flask": {
        "overview": "Cold ve freeze savunmasi icin nis taban.",
        "suffixes": ("freeze", "curse", "movement", "resistance", "shock"),
    },
    "Iron Flask": {
        "overview": "Ward odakli nis taban; genel utility suffixleriyle deger kazanir.",
        "suffixes": ("movement", "curse", "resistance", "stun", "armour"),
    },
}

LIFE_FLASKS = {
    "Divine Life Flask": {
        "overview": "Instant recovery icin en cok kullanilan endgame life flask tabani.",
        "combinations": (
            {
                "title": "Seething + Assuaging",
                "prefix": "Seething | 66% reduced Amount Recovered / Instant Recovery",
                "suffix": "of Assuaging | Bleeding ve Corrupted Blood immunity",
                "min_item_level": 80,
                "why": "En hizli panik butonu ve en likit genel kombinasyon.",
                "finish": "20% quality. Instilling enchant build tercihine gore sonradan uygulanir.",
            },
            {
                "title": "Bubbling + Assuaging",
                "prefix": "Bubbling | 50% of Recovery applied Instantly",
                "suffix": "of Assuaging | Bleeding ve Corrupted Blood immunity",
                "min_item_level": 80,
                "why": "Instant tepkiyi korurken Seething'den daha fazla toplam life verir.",
                "finish": "20% quality. Genel kullanim icin en dengeli life flask seceneklerinden.",
            },
            {
                "title": "Saturated + Perenniality",
                "prefix": "Saturated | (65-70)% increased Amount Recovered",
                "suffix": "of Perenniality | ek recovery 10 saniyeye yayilir",
                "min_item_level": 81,
                "why": "Uzun sureli sustain isteyen buildler icin yuksek toplam recovery.",
                "finish": "20% quality. Instant flask degil; surekli sustain amaclidir.",
            },
            {
                "title": "Catalysed + Perenniality",
                "prefix": "Catalysed | (65-70)% increased Recovery rate",
                "suffix": "of Perenniality | ek recovery 10 saniyeye yayilir",
                "min_item_level": 81,
                "why": "Daha hizli ana recovery ile uzun sureli ek recovery'yi birlestirir.",
                "finish": "20% quality. Sustain odakli alternatif.",
            },
        ),
    },
    "Eternal Life Flask": {
        "overview": "Daha uzun recovery davranisi isteyen buildler icin life flask alternatifi.",
        "combinations": (
            {
                "title": "Bubbling + Assuaging",
                "prefix": "Bubbling | 50% of Recovery applied Instantly",
                "suffix": "of Assuaging | Bleeding ve Corrupted Blood immunity",
                "min_item_level": 80,
                "why": "Uzun taban suresiyle dengeli instant recovery sunar.",
                "finish": "20% quality. Instilling enchant build tercihine gore uygulanir.",
            },
            {
                "title": "Saturated + Perenniality",
                "prefix": "Saturated | (65-70)% increased Amount Recovered",
                "suffix": "of Perenniality | ek recovery 10 saniyeye yayilir",
                "min_item_level": 81,
                "why": "Yuksek toplam recovery ve uzun sustain icin.",
                "finish": "20% quality. Instant degil, sustain odaklidir.",
            },
        ),
    },
}


def flask_types() -> tuple[str, ...]:
    """Return guide-supported flask bases in display order."""
    return tuple(UTILITY_FLASKS) + tuple(LIFE_FLASKS)


def guide_for(base_name: str) -> dict:
    """Return a normalized guide record for a supported flask base."""
    if base_name in UTILITY_FLASKS:
        spec = UTILITY_FLASKS[base_name]
        combinations = []
        for suffix_key in spec["suffixes"]:
            suffix = UTILITY_SUFFIXES[suffix_key]
            combinations.append(
                {
                    "title": f"25% Effect + {suffix['affix']}",
                    "prefix": f"{UTILITY_PREFIX['affix']} | {UTILITY_PREFIX['text']}",
                    "suffix": f"{suffix['affix']} | {suffix['text']}",
                    "min_item_level": max(UTILITY_PREFIX["level"], suffix["level"]),
                    "why": suffix["why"],
                    "finish": (
                        "20% quality. Mageblood icin 70% increased effect Enkindling "
                        "enchant kullanilabilir. Bos suffix alternatifi: bench'ten "
                        "%3 Life Regeneration during Effect."
                    ),
                }
            )
        return {
            "base": base_name,
            "overview": spec["overview"],
            "combinations": tuple(combinations),
            "offline": True,
        }

    if base_name in LIFE_FLASKS:
        spec = LIFE_FLASKS[base_name]
        return {
            "base": base_name,
            "overview": spec["overview"],
            "combinations": tuple(dict(combo) for combo in spec["combinations"]),
            "offline": True,
        }

    raise KeyError(f"Unsupported flask base: {base_name}")
