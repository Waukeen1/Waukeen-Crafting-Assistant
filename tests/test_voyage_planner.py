import ast
from pathlib import Path

from voyage_planner import (
    Chart,
    auto_calibration_points,
    border_cell_scores,
    chart_position_score,
    catalog_entry_score,
    chart_slot_occupied,
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
    right_click_rotations_between,
    scale_calibration_points,
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


def test_chart_slot_occupancy_detects_green_icon_and_rejects_empty_cell():
    image = Image.new("RGB", (120, 60), (12, 14, 13))
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 15, 39, 39), fill=(25, 135, 82))
    assert chart_slot_occupied(image, (27, 27))
    assert not chart_slot_occupied(image, (90, 27))


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


def test_carried_chart_right_click_rotation_is_counter_clockwise():
    west = (False, False, False, True)
    north = (True, False, False, False)
    east_west = (False, True, False, True)
    north_south = (True, False, True, False)

    assert right_click_rotations_between(west, north, "end") == 3
    assert right_click_rotations_between(north, west, "end") == 1
    assert right_click_rotations_between(east_west, north_south, "straight") == 1
    assert right_click_rotations_between((True,) * 4, (True,) * 4, "crossing") == 0


def test_detect_chart_edges_reads_dark_gaps_for_every_shape_rotation():
    center = (70, 70)
    base_edges = {
        "end": (True, False, False, False),
        "corner": (True, True, False, False),
        "straight": (True, False, True, False),
        "junction": (True, True, True, False),
        "crossing": (True, True, True, True),
    }
    for shape, base in base_edges.items():
        for rotations in range(4):
            edges = rotate_edges(base, rotations)
            image = Image.new("RGB", (140, 140), (35, 30, 22))
            draw = ImageDraw.Draw(image)
            for active, (dx, dy) in zip(
                edges,
                ((0, -1), (1, 0), (0, 1), (-1, 0)),
            ):
                if not active:
                    draw.line(
                        (
                            center[0],
                            center[1],
                            center[0] + dx * 10,
                            center[1] + dy * 10,
                        ),
                        fill=(30, 240, 100),
                        width=5,
                    )
            assert detect_chart_edges(image, center, shape) == edges


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


def test_detect_board_edges_tolerates_calibrated_center_offset():
    center = (90, 90)
    ink_center = (center[0] + 4, center[1] + 6)
    for edges in (
        (True, False, True, False),
        (False, True, False, True),
    ):
        image = Image.new("RGB", (180, 180), (220, 205, 170))
        draw = ImageDraw.Draw(image)
        for active, (dx, dy) in zip(
            edges,
            ((0, -1), (1, 0), (0, 1), (-1, 0)),
        ):
            if active:
                draw.line(
                    (
                        ink_center[0],
                        ink_center[1],
                        ink_center[0] + dx * 62,
                        ink_center[1] + dy * 62,
                    ),
                    fill=(18, 15, 12),
                    width=5,
                )
        assert detect_board_edges(image, center, "straight", 143) == edges


def test_auto_calibration_uses_client_height_and_center():
    full_hd = auto_calibration_points((0, 0, 1920, 1080))
    assert full_hd == {
        "chart_tl": (1312, 312),
        "chart_br": (1567, 766),
        "board_tl": (791, 395),
        "board_br": (1083, 683),
    }

    scaled = auto_calibration_points((100, 50, 1636, 914))
    assert scaled == {
        "chart_tl": (1150, 300),
        "chart_br": (1354, 663),
        "board_tl": (733, 366),
        "board_br": (966, 596),
    }


def test_auto_calibration_rejects_tiny_or_invalid_clients():
    assert auto_calibration_points((0, 0, 800, 450)) is None
    assert auto_calibration_points((10, 10, 10, 10)) is None


def test_manual_calibration_scales_with_client_resolution_and_offset():
    points = {
        "chart_tl": (1312, 312),
        "chart_br": (1567, 766),
        "board_tl": (791, 395),
        "board_br": (1083, 683),
    }
    assert scale_calibration_points(
        points,
        (0, 0, 1920, 1080),
        (100, 50, 2660, 1490),
    ) == {
        "chart_tl": (1849, 466),
        "chart_br": (2189, 1071),
        "board_tl": (1155, 577),
        "board_br": (1544, 961),
    }


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
    order = placement_order(plan)
    assert len(order) == 9
    assert len({placement.cell for placement in order}) == 9
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


def test_divine_corner_uses_both_adjacent_cells_for_best_rare_sources():
    charts = [
        chart(
            "boxes",
            "crossing",
            ("Adjacent Areas contain 5 additional Strongboxes",),
        ),
        chart(
            "rares",
            "crossing",
            ("60% increased number of Rare Monsters",),
        ),
        chart(
            "global-rares",
            "crossing",
            ("25% increased number of Rare Monsters",),
        ),
        chart(
            "fracture",
            "crossing",
            ("50% chance for Rare Monsters to Fracture on death",),
        ),
    ]
    charts.extend(chart(f"junk-{index}", "crossing") for index in range(5))
    border = [()] * 9
    border[0] = ("Rare Monsters in Area drop an additional Divine Orb",)

    plan = plan_voyage(charts, border)

    assert plan is not None
    by_uid = {placement.chart.uid: placement.cell for placement in plan.placements}
    assert {by_uid["boxes"], by_uid["rares"]} == {1, 3}
    assert "Rare-drop anchors optimized: 1" in plan.notes


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


def test_fracture_is_magic_density_not_additional_rares():
    catalog = modifier_catalog()
    fracture = next(
        entry for entry in catalog["chart_global"] if entry["id"] == "voy-fracture"
    )
    global_rares = next(
        entry for entry in catalog["chart_global"] if entry["id"] == "voy-rare"
    )

    assert fracture["effects"] == [{"stat": "magicmonsters", "percent": 50}]
    assert catalog_entry_score(fracture) < catalog_entry_score(global_rares) * 2


def test_fracture_does_not_move_towards_divine_border():
    fracture = chart(
        "fracture",
        "crossing",
        ("50% chance for Rare Monsters to Fracture on death",),
    )
    borders = [()] * 9
    borders[0] = ("Rare Monsters in Area drop an additional Divine Orb",)
    scores = border_cell_scores(borders)

    assert chart_position_score(fracture, 0, borders, scores) == chart_position_score(
        fracture, 8, borders, scores
    )


def test_divine_border_strongboxes_beat_plain_adjacent_rares():
    strongboxes = chart(
        "boxes",
        "crossing",
        ("Adjacent Areas contain 5 additional Strongboxes",),
    )
    rare_percent = chart(
        "rares",
        "crossing",
        ("60% increased number of Rare Monsters",),
    )
    borders = [()] * 9
    borders[0] = ("Rare Monsters in Area drop an additional Divine Orb",)
    scores = border_cell_scores(borders)

    assert chart_position_score(strongboxes, 1, borders, scores) > chart_position_score(
        rare_percent, 1, borders, scores
    )


def test_divine_border_connection_rare_bonus_changes_topology_score():
    borders = [()] * 9
    borders[1] = (
        "Rare Monsters in Area drop an additional Divine Orb",
        "50% increased number of Rare monsters in Area per Chart connection",
    )
    charts = []
    for shape in ("end", "corner", "straight", "junction", "crossing"):
        charts.extend(chart(f"{shape}-{index}", shape) for index in range(9))

    plan = plan_voyage(charts, borders)

    assert plan is not None
    anchor = plan.placement_for_cell(1)
    internal_connections = sum(
        anchor.required_edges[direction]
        for direction, _ in cell_neighbors(1)
    )
    assert internal_connections == 3


def test_live_placement_clicks_source_then_target_then_rotates_target():
    source_path = Path(__file__).parents[1] / "cluster_craft.pyw"
    module = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    place_plan = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_voyage_place_plan"
    )
    calls = [
        node.func.id
        for node in ast.walk(place_plan)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]

    assert "_voyage_rotate_placed" not in calls
    assert "_voyage_validate_placed_cell" in calls
    assert "_voyage_drag_safely" not in calls
    assert "_voyage_required_source_rotations" not in calls
    plan_source = ast.get_source_segment(
        source_path.read_text(encoding="utf-8-sig"),
        place_plan,
    )
    assert plan_source.index("_voyage_place_chart") < plan_source.index(
        "_voyage_validate_placed_cell"
    )

    place_chart = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_voyage_place_chart"
    )
    place_source = ast.get_source_segment(
        source_path.read_text(encoding="utf-8-sig"),
        place_chart,
    )
    assert "mouseDown" not in place_source
    assert "mouseUp" not in place_source
    assert place_source.count('_voyage_click("left")') == 2
    assert place_source.count('_voyage_click(\n            "right"') == 1
    assert "ImageGrab.grab(all_screens=True)" in place_source
    assert "updated_edges == current_edges" in place_source
    assert "cell_span * 0.65" in place_source
    assert "hover_origin=hover_origin" in place_source


def test_live_scan_validates_scaled_borders_before_chart_inventory():
    source_path = Path(__file__).parents[1] / "cluster_craft.pyw"
    source = source_path.read_text(encoding="utf-8-sig")
    module = ast.parse(source)
    runner = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_voyage_craft"
    )
    runner_source = ast.get_source_segment(source, runner)
    assert runner_source.index("_voyage_scan_borders") < runner_source.index(
        "_voyage_scan_chart_pages"
    )
    border_scanner = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_voyage_scan_borders"
    )
    border_source = ast.get_source_segment(source, border_scanner)
    assert "crop_pad_x = round(430 * board_scale)" in border_source
    assert "crop_pad_y = round(180 * board_scale)" in border_source
    place_chart = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_voyage_place_chart"
    )
    place_source = ast.get_source_segment(source, place_chart)
    assert "cell_span * 0.65" in place_source
    assert "_voyage_source_patch" not in place_source
    assert place_source.count("_instant_move") == 2
    assert (
        place_source.rindex('_voyage_click("left")')
        < place_source.index('_voyage_click(\n            "right"')
    )

    click_fn = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_voyage_click"
    )
    click_source = ast.get_source_segment(
        source_path.read_text(encoding="utf-8-sig"),
        click_fn,
    )
    assert "SendInput" in click_source
    assert "mouse_event" not in click_source
    assert "send_absolute(hover_origin)" in click_source
    assert "send_absolute(approach)" not in click_source
    assert "send_absolute(point)" in click_source
    assert "0xC001" in click_source
