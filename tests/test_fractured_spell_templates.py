import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "itemcraft" / "L12 - Spell - Frac Stat - ilvl84.json",
    ROOT / "itemcraft" / "L12 - Spell - Frac 35 Effect - ilvl84.json",
)


def test_fractured_spell_templates_have_valid_four_affix_combos():
    for path in TEMPLATES:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["cluster_fracture_mode"] == "fractured"
        assert data["use_exalt"] is True
        assert data["use_annul"] is True
        assert len(data["comb_craft_data"]) == 12
        for combo in data["comb_craft_data"].values():
            assert len(combo) == 4
            assert sum(target.startswith("[P]") for target in combo) == 2
            assert sum(target.startswith("[S]") for target in combo) == 2
            assert any("increased Effect(35)" in target for target in combo)


def test_effect_fracture_template_requires_the_effect_fracture():
    data = json.loads(TEMPLATES[1].read_text(encoding="utf-8"))
    assert "increased Effect(35)" in data["cluster_fractured_target"]
