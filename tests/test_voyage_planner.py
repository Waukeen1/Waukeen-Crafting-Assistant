from voyage_planner import (
    Chart,
    border_cell_scores,
    chart_position_score,
    cell_neighbors,
    detect_chart_edges,
    detect_board_edges,
    is_connected,
    match_catalog_entries,
    modifier_catalog,
    parse_chart_text,
    placement_order,
    plan_voyage,
    required_edges_from_mask,
    rotate_edges,
)
from PIL import Image, ImageDraw


def chart(uid, shape, mods=(), level=83):
    return Chart(
        uid=uid,
        shape=shape,
        area_level=level,
        raw_text="",
        modifiers=tuple(mods),
        initial_edges=None,
    )


def test_parse_chart_text():
    parsed = parse_chart_text(
        """Item Class: Chart
Rarity: Rare
Sunken Chart
--------
Area Level: 83
Chart Shape: Junction
--------
22% increased Pack Size
Adjacent Areas contain 40% increased number of Rare Monsters
""",
        "slot-1",
        (100, 200),
    )
    assert parsed is not None
    assert parsed.shape == "junction"
    assert parsed.area_level == 83
    assert parsed.source == (100, 200)
    assert "22% increased Pack Size" in parsed.modifiers


def test_static_modifier_catalog_is_complete():
    catalog = modifier_catalog()
    assert len(catalog["chart_self"]) == 15
    assert len(catalog["chart_adjacent"]) == 42
    assert len(catalog["chart_global"]) == 19
    assert len(catalog["border"]) == 64


def test_border_catalog_tolerates_ocr_percent_error():
    matched = match_catalog_entries(
        "Adjacent Areas have 6096 increased explicit modifier magnitudes",
        ("border",),
    )
    assert any(entry["id"] == "b-mag-2" for entry in matched)


def test_rotation_is_clockwise():
    assert rotate_edges((True, False, False, False), 1) == (
        False,
        True,
        False,
        False,
    )


def test_detect_board_edges_reads_each_rotation():
    center = (90, 90)
    for shape in ("end", "corner", "straight", "junction", "crossing"):
        for rotations in range(4):
            edges = rotate_edges(
                {
                    "end": (True, False, False, False),
                    "corner": (True, True, False, False),
                    "straight": (True, False, True, False),
                    "junction": (True, True, True, False),
                    "crossing": (True, True, True, True),
                }[shape],
                rotations,
            )
            image = Image.new("RGB", (180, 180), (220, 205, 170))
            draw = ImageDraw.Draw(image)
            for active, (dx, dy) in zip(edges, ((0, -1), (1, 0), (0, 1), (-1, 0))):
                if active:
                    draw.line(
                        (
                            center[0],
                            center[1],
                            center[0] + dx * 62,
                            center[1] + dy * 62,
                        ),
                        fill=(18, 15, 12),
                        width=5,
                    )
            assert detect_board_edges(image, center, shape, 143) == edges


def test_disconnected_edge_mask_is_rejected():
    assert not is_connected(required_edges_from_mask(0))


def test_planner_builds_connected_nine_chart_route():
    charts = []
    for shape, count in {
        "end": 9,
        "corner": 9,
        "straight": 9,
        "junction": 9,
        "crossing": 3,
    }.items():
        charts.extend(chart(f"{shape}-{i}", shape) for i in range(count))
    plan = plan_voyage(charts, [()] * 9)
    assert plan is not None
    assert len(plan.placements) == 9
    assert len(placement_order(plan)) == 9
    assert len({placement.chart.uid for placement in plan.placements}) == 9


def test_planner_allows_routes_to_extend_outside_board():
    charts = []
    for shape, count in {
        "end": 3,
        "corner": 1,
        "straight": 16,
        "junction": 1,
        "crossing": 26,
    }.items():
        charts.extend(chart(f"{shape}-{i}", shape) for i in range(count))

    plan = plan_voyage(charts, [()] * 9)

    assert plan is not None
    assert len(plan.placements) == 9
    assert len(placement_order(plan)) == 9
    by_cell = {placement.cell: placement for placement in plan.placements}
    for cell, placement in by_cell.items():
        for direction, neighbour in cell_neighbors(cell):
            opposite = (direction + 2) % 4
            assert (
                placement.required_edges[direction]
                == by_cell[neighbour].required_edges[opposite]
            )


def test_outside_edges_do_not_count_as_connections():
    charts = [chart(f"crossing-{index}", "crossing") for index in range(9)]
    plan = plan_voyage(charts, [()] * 9)
    assert plan is not None

    top_left = plan.placement_for_cell(0)
    assert top_left.required_edges[0]
    assert top_left.required_edges[3]
    internal_connections = sum(
        top_left.required_edges[direction]
        for direction, _ in cell_neighbors(0)
    )
    assert internal_connections == 2


def test_divine_border_prefers_rare_support_near_anchor():
    charts = []
    for shape in ("end", "corner", "straight", "junction"):
        for i in range(12):
            mods = ()
            if i == 0:
                mods = (
                    "Adjacent Areas have 75% increased number of Rare Monsters",
                )
            charts.append(chart(f"{shape}-{i}", shape, mods))
    charts.extend(chart(f"crossing-{i}", "crossing") for i in range(4))
    border = [()] * 9
    border[0] = ("Rare Monsters in Area drop an additional Divine Orb",)
    plan = plan_voyage(charts, border)
    assert plan is not None
    rare_support_cells = {
        p.cell
        for p in plan.placements
        if "Rare Monsters" in " ".join(p.chart.modifiers)
    }
    assert rare_support_cells.intersection({1, 3})


def test_adjacent_modifier_prefers_more_affected_areas():
    adjacent_chart = chart(
        "adjacent",
        "crossing",
        ("Adjacent Areas contain 5 additional Strongboxes",),
    )
    borders = [()] * 9
    scores = border_cell_scores(borders)

    corner = chart_position_score(adjacent_chart, 0, borders, scores)
    edge = chart_position_score(adjacent_chart, 1, borders, scores)
    center = chart_position_score(adjacent_chart, 4, borders, scores)

    assert center > edge > corner


def test_global_modifier_position_value_is_constant():
    global_chart = chart(
        "global",
        "crossing",
        ("25% increased number of Rare Monsters in all Voyage Areas",),
    )
    borders = [()] * 9
    scores = border_cell_scores(borders)

    values = {
        chart_position_score(global_chart, cell, borders, scores)
        for cell in range(9)
    }
    assert len(values) == 1
