"""Pure planning helpers for the Allflame Voyage board."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
import json
import os
import re
from typing import Iterable, Sequence


N, E, S, W = range(4)
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))
START_CELL = 6

SHAPE_BY_DEGREE = {
    1: "end",
    3: "junction",
    4: "crossing",
}

SHAPE_ALIASES = {
    "end": "end",
    "corner": "corner",
    "straight": "straight",
    "junction": "junction",
    "cross": "crossing",
    "crossing": "crossing",
    "crossroads": "crossing",
}

BASE_EDGES = {
    "end": (True, False, False, False),
    "corner": (True, True, False, False),
    "straight": (True, False, True, False),
    "junction": (True, True, True, False),
    "crossing": (True, True, True, True),
}

STAT_WEIGHTS = {
    "currency": 1.65,
    "divcards": 1.35,
    "scarabs": 1.25,
    "treasure": 1.05,
    "packsize": 1.15,
    "quantity": 1.0,
    "rares": 1.2,
    "magicmonsters": 0.55,
    "preserve": 0.75,
    "sulphur": 0.18,
    "gold": 0.1,
    "rarity": 0.14,
    "uniques": 0.4,
    "essences": 0.18,
    "spirits": 0.4,
    "wisps": 0.35,
    "exp": 0.12,
}

SPECIAL_ENTRY_SCORES = {
    "voy-noequip": 35.0,
    "voy-jelly": 18.0,
    "voy-soul": -8.0,
    "voy-flask": 0.0,
}

# Reference offsets are relative to the centre of a 1920x1080 PoE client.
# Scaling by client height also works for ultrawide displays because the Voyage
# panel keeps its aspect and remains centred in the game client.
VOYAGE_REFERENCE_HEIGHT = 1080.0
VOYAGE_REFERENCE_OFFSETS = {
    "chart_tl": (352.0, -228.0),
    "chart_br": (607.0, 226.0),
    "board_tl": (-169.0, -145.0),
    "board_br": (123.0, 143.0),
}


def auto_calibration_points(client_rect: Sequence[int]):
    """Return Voyage grid points scaled to the active PoE client rectangle."""
    if not client_rect or len(client_rect) != 4:
        return None
    left, top, right, bottom = (int(value) for value in client_rect)
    width, height = right - left, bottom - top
    if width < 960 or height < 540:
        return None
    scale = height / VOYAGE_REFERENCE_HEIGHT
    center_x = left + width / 2.0
    center_y = top + height / 2.0
    points = {
        name: (
            round(center_x + offset_x * scale),
            round(center_y + offset_y * scale),
        )
        for name, (offset_x, offset_y) in VOYAGE_REFERENCE_OFFSETS.items()
    }
    if not all(
        left <= x < right and top <= y < bottom
        for x, y in points.values()
    ):
        return None
    return points


def scale_calibration_points(points, old_client_rect, new_client_rect):
    """Map manually calibrated client-relative points to a new PoE client."""
    if not points or not all(points.values()):
        return points
    if not old_client_rect or not new_client_rect:
        return points
    old_left, old_top, old_right, old_bottom = map(int, old_client_rect)
    new_left, new_top, new_right, new_bottom = map(int, new_client_rect)
    old_width, old_height = old_right - old_left, old_bottom - old_top
    new_width, new_height = new_right - new_left, new_bottom - new_top
    if min(old_width, old_height, new_width, new_height) <= 0:
        return points
    scale_x = new_width / old_width
    scale_y = new_height / old_height
    return {
        name: (
            round(new_left + (point[0] - old_left) * scale_x),
            round(new_top + (point[1] - old_top) * scale_y),
        )
        for name, point in points.items()
    }


@dataclass(frozen=True)
class Chart:
    uid: str
    shape: str
    area_level: int
    raw_text: str
    modifiers: tuple[str, ...]
    source: tuple[int, int] | None = None
    source_page: int = 1
    initial_edges: tuple[bool, bool, bool, bool] | None = None


@dataclass(frozen=True)
class Placement:
    cell: int
    chart: Chart
    required_edges: tuple[bool, bool, bool, bool]
    rotations: int
    score: float


@dataclass
class VoyagePlan:
    placements: list[Placement]
    score: float
    edge_mask: int
    notes: list[str] = field(default_factory=list)

    def placement_for_cell(self, cell: int) -> Placement:
        return next(p for p in self.placements if p.cell == cell)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\r", " ")).strip().lower()


def _modifier_fingerprint(value: str) -> str:
    normalized = normalize_text(value)
    normalized = re.sub(r"\b(\d{1,3})96\b", r"\1%", normalized)
    normalized = re.sub(r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?%?", "#", normalized)
    normalized = re.sub(r"[^a-z#]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


@lru_cache(maxsize=1)
def modifier_catalog():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "voyage_modifiers.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {
            "chart_self": [],
            "chart_adjacent": [],
            "chart_global": [],
            "border": [],
        }


def _line_similarity(target: str, raw_lines: Sequence[str]) -> float:
    target_normalized = normalize_text(target)
    return max(
        (
            SequenceMatcher(None, target_normalized, normalize_text(line)).ratio()
            for line in raw_lines
            if line.strip()
        ),
        default=0.0,
    )


def match_catalog_entries(text: str, sections: Sequence[str]):
    raw_lines = tuple(line.strip() for line in (text or "").splitlines() if line.strip())
    raw_normalized = normalize_text(text)
    raw_fingerprint = _modifier_fingerprint(text)
    groups = {}
    for section in sections:
        for entry in modifier_catalog().get(section, ()):
            groups.setdefault(_modifier_fingerprint(entry.get("text", "")), []).append(entry)

    matched = []
    for fingerprint, entries in groups.items():
        if not fingerprint:
            continue
        exact = [
            entry
            for entry in entries
            if normalize_text(entry.get("text", "")) in raw_normalized
        ]
        if exact:
            matched.append(max(exact, key=lambda entry: len(entry.get("text", ""))))
            continue
        if fingerprint not in raw_fingerprint:
            continue
        best_entry = max(
            entries,
            key=lambda entry: _line_similarity(entry.get("text", ""), raw_lines),
        )
        if _line_similarity(best_entry.get("text", ""), raw_lines) >= 0.62:
            matched.append(best_entry)
    return matched


def _effects_score(effects: Iterable[dict]) -> float:
    return sum(
        float(effect.get("percent", 0.0))
        * STAT_WEIGHTS.get(str(effect.get("stat", "")).lower(), 0.0)
        for effect in effects
    )


def catalog_entry_score(entry: dict, connections: int = 0) -> float:
    score = _effects_score(entry.get("effects", ()))
    score += _effects_score(entry.get("perConnEffects", ())) * connections
    score += float(entry.get("magnitude", 0.0)) * 0.65
    score += SPECIAL_ENTRY_SCORES.get(entry.get("id"), 0.0)
    return score


def parse_chart_text(
    text: str,
    uid: str,
    source: tuple[int, int] | None = None,
    initial_edges: tuple[bool, bool, bool, bool] | None = None,
    source_page: int = 1,
) -> Chart | None:
    if not text or not re.search(r"Item Class:\s*Chart\b", text, re.I):
        return None
    if re.search(r"Voyage Modifier will be revealed once Charted", text, re.I):
        return None

    shape_match = re.search(r"Chart Shape:\s*([A-Za-z ]+)", text, re.I)
    level_match = re.search(r"Area Level:\s*(\d+)", text, re.I)
    if not shape_match or not level_match:
        return None
    shape_raw = normalize_text(shape_match.group(1))
    shape = next(
        (canonical for alias, canonical in SHAPE_ALIASES.items() if alias in shape_raw),
        "",
    )
    if not shape:
        return None

    ignored_prefixes = (
        "item class:",
        "rarity:",
        "chart shape:",
        "area level:",
        "item level:",
        "requirements:",
        "note:",
    )
    modifiers: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        low = normalize_text(line)
        if not line or line == "--------" or line.startswith("{"):
            continue
        if any(low.startswith(prefix) for prefix in ignored_prefixes):
            continue
        if low in {"chart", "normal", "magic", "rare"}:
            continue
        modifiers.append(line)

    return Chart(
        uid=uid,
        shape=shape,
        area_level=int(level_match.group(1)),
        raw_text=text,
        modifiers=tuple(modifiers),
        source=source,
        source_page=int(source_page),
        initial_edges=initial_edges,
    )


def chart_slot_occupied(image, point, radius=14):
    """Detect the green Chart icon without hovering or reading the clipboard."""
    source = image.convert("RGB")
    center_x, center_y = (int(point[0]), int(point[1]))
    green_pixels = 0
    for y in range(max(0, center_y - radius), min(source.height, center_y + radius + 1)):
        for x in range(max(0, center_x - radius), min(source.width, center_x + radius + 1)):
            red, green, blue = source.getpixel((x, y))
            if green > 60 and green > red * 1.12 and green > blue * 0.8:
                green_pixels += 1
    return green_pixels >= 18


def rotate_edges(
    edges: Sequence[bool], rotations: int
) -> tuple[bool, bool, bool, bool]:
    rotations %= 4
    return tuple(bool(edges[(i - rotations) % 4]) for i in range(4))


def rotations_between(
    initial: Sequence[bool] | None,
    required: Sequence[bool],
    shape: str,
) -> int:
    start = tuple(initial) if initial else BASE_EDGES[shape]
    target = tuple(required)
    for rotations in range(4):
        if rotate_edges(start, rotations) == target:
            return rotations
    raise ValueError(f"{shape} cannot satisfy edge pattern {target}")


def right_click_rotations_between(
    initial: Sequence[bool] | None,
    required: Sequence[bool],
    shape: str,
) -> int:
    """Return clicks for PoE's counter-clockwise carried-chart rotation."""
    clockwise = rotations_between(initial, required, shape)
    canonical = SHAPE_ALIASES.get(normalize_text(shape), normalize_text(shape))
    period = 1 if canonical == "crossing" else 2 if canonical == "straight" else 4
    return (-clockwise) % period


def detect_chart_edges(image, point: tuple[int, int], shape: str):
    """Read icon openings. Green square-border gaps are chart connections."""
    canonical = SHAPE_ALIASES.get(normalize_text(shape), normalize_text(shape))
    degree = sum(BASE_EDGES.get(canonical, ()))
    if degree == 4:
        return (True, True, True, True)
    if degree <= 0:
        return None

    px = image.convert("RGB").load()
    width, height = image.size
    expected = degree
    best = None

    # The hover coordinate can be a few pixels off the glyph's visual center.
    for ox in range(-4, 5):
        for oy in range(-4, 5):
            cx, cy = int(point[0] + ox), int(point[1] + oy)
            values = []
            valid = True
            for dx, dy in DIRS:
                samples = []
                for radius in range(3, 10):
                    for tangent in (-1, 0, 1):
                        x = cx + dx * radius + (tangent if dy else 0)
                        y = cy + dy * radius + (tangent if dx else 0)
                        if not (0 <= x < width and 0 <= y < height):
                            valid = False
                            break
                        r, g, b = px[x, y]
                        samples.append(g - ((r + b) / 2.0))
                    if not valid:
                        break
                if not valid:
                    break
                values.append(sum(samples) / max(1, len(samples)))
            if not valid:
                continue
            for rotation in range(4):
                candidate_edges = rotate_edges(BASE_EDGES[canonical], rotation)
                if rotation and candidate_edges == BASE_EDGES[canonical]:
                    continue
                openings = [
                    values[index]
                    for index, active in enumerate(candidate_edges)
                    if active
                ]
                closed = [
                    values[index]
                    for index, active in enumerate(candidate_edges)
                    if not active
                ]
                # Open route sides are dark gaps in the green Chart glyph.
                # This predicts the route that appears after placement.
                open_mean = sum(openings) / max(1, len(openings))
                closed_mean = (
                    sum(closed) / len(closed) if closed else open_mean + 1.0
                )
                quality = (
                    closed_mean
                    - open_mean
                    - (abs(ox) + abs(oy)) * 0.35
                )
                if best is None or quality > best[0]:
                    best = (quality, candidate_edges)
    return best[1] if best else None


def detect_board_edges(
    image,
    point: tuple[int, int],
    shape: str,
    cell_span: float = 143.0,
):
    """Read the dark route drawn on a placed Voyage board Chart."""
    canonical = SHAPE_ALIASES.get(normalize_text(shape), normalize_text(shape))
    degree = sum(BASE_EDGES.get(canonical, ()))
    if degree == 4:
        return (True, True, True, True)
    if degree <= 0:
        return None

    source = image.convert("RGB")
    px = source.load()
    width, height = source.size
    ray_start = max(8, round(cell_span * 0.08))
    ray_end = max(ray_start + 8, round(cell_span * 0.40))
    cx, cy = int(point[0]), int(point[1])
    best = None
    # Calibrated board points can be several pixels away from the ink centre.
    # Search a small neighbourhood so a horizontal route is not missed merely
    # because its thin line sits outside the old +/-2 tangent strip.
    offsets = range(-8, 9, 2)
    for ox in offsets:
        for oy in offsets:
            values = []
            valid = True
            for dx, dy in DIRS:
                samples = []
                for radius in range(ray_start, ray_end + 1):
                    for tangent in (-2, -1, 0, 1, 2):
                        x = cx + ox + dx * radius + (tangent if dy else 0)
                        y = cy + oy + dy * radius + (tangent if dx else 0)
                        if not (0 <= x < width and 0 <= y < height):
                            valid = False
                            break
                        r, g, b = px[x, y]
                        samples.append(255 - max(r, g, b))
                    if not valid:
                        break
                if not valid:
                    break
                values.append(sum(samples) / max(1, len(samples)))
            if not valid:
                continue

            seen = set()
            for rotation in range(4):
                candidate = rotate_edges(BASE_EDGES[canonical], rotation)
                if candidate in seen:
                    continue
                seen.add(candidate)
                active = [
                    values[index]
                    for index, enabled in enumerate(candidate)
                    if enabled
                ]
                inactive = [
                    values[index]
                    for index, enabled in enumerate(candidate)
                    if not enabled
                ]
                score = sum(active) / len(active)
                if inactive:
                    score -= sum(inactive) / len(inactive)
                if best is None or score > best[0]:
                    best = (score, candidate)
    return best[1] if best else None


def cell_neighbors(cell: int):
    row, col = divmod(cell, 3)
    for direction, (dx, dy) in enumerate(DIRS):
        nr, nc = row + dy, col + dx
        if 0 <= nr < 3 and 0 <= nc < 3:
            yield direction, nr * 3 + nc


def required_edges_from_mask(mask: int):
    edges = [[False] * 4 for _ in range(9)]
    bit = 0
    for row in range(3):
        for col in range(2):
            left = row * 3 + col
            right = left + 1
            if mask & (1 << bit):
                edges[left][E] = True
                edges[right][W] = True
            bit += 1
    for row in range(2):
        for col in range(3):
            top = row * 3 + col
            bottom = top + 3
            if mask & (1 << bit):
                edges[top][S] = True
                edges[bottom][N] = True
            bit += 1
    return tuple(tuple(row) for row in edges)


def is_connected(edges, start: int = START_CELL) -> bool:
    seen = {start}
    pending = [start]
    while pending:
        cell = pending.pop()
        for direction, other in cell_neighbors(cell):
            if edges[cell][direction] and other not in seen:
                seen.add(other)
                pending.append(other)
    return len(seen) == 9


def shape_for_edges(edges: Sequence[bool]) -> str | None:
    degree = sum(bool(v) for v in edges)
    if degree == 2:
        return "straight" if (edges[N] and edges[S]) or (edges[E] and edges[W]) else "corner"
    return SHAPE_BY_DEGREE.get(degree)


def compatible_orientations(
    shape: str,
    cell: int,
    internal_edges: Sequence[bool],
):
    """Return rotations that match every in-board edge.

    Connections that point outside the 3x3 board are harmless. Inside the
    board, both neighbouring Charts must still agree on the shared edge.
    """
    orientations = []
    seen = set()
    internal_directions = {direction for direction, _ in cell_neighbors(cell)}
    for rotations in range(4):
        edges = rotate_edges(BASE_EDGES[shape], rotations)
        if edges in seen:
            continue
        seen.add(edges)
        if all(
            edges[direction] == bool(internal_edges[direction])
            for direction in internal_directions
        ):
            orientations.append(edges)
    return tuple(orientations)


@lru_cache(maxsize=1)
def valid_topologies():
    result = []
    for mask in range(1 << 12):
        edges = required_edges_from_mask(mask)
        if not is_connected(edges):
            continue
        shapes = tuple(shape_for_edges(edge_set) for edge_set in edges)
        if all(shapes):
            result.append((mask, edges, shapes))
    return tuple(result)


def _number_before(text: str, phrase: str, default: float = 0.0) -> float:
    match = re.search(rf"(\d+(?:\.\d+)?)%?\s+{phrase}", text, re.I)
    return float(match.group(1)) if match else default


def _keyword_score(text: str) -> float:
    low = normalize_text(text)
    score = 0.0
    weighted = (
        ("additional divine orb", 260),
        ("divine orb", 180),
        ("stacked deck", 105),
        ("operative", 85),
        ("arcanist", 72),
        ("diviner", 72),
        ("currency", 56),
        ("scarab", 48),
        ("strongbox", 38),
        ("golden lantern", 38),
        ("rare monster", 35),
        ("altar", 32),
        ("pack size", 28),
        ("additional pack", 24),
        ("map", 20),
        ("item quantity", 20),
        ("quantity of items", 20),
        ("item rarity", 7),
        ("essence", 5),
        ("equipment quality", -24),
        ("flask quality", -24),
        ("tincture quality", -24),
    )
    for phrase, weight in weighted:
        if phrase in low:
            score += weight
    score += _number_before(low, r"increased pack size") * 0.9
    score += _number_before(low, r"increased quantity") * 0.45
    score += _number_before(low, r"increased rarity") * 0.08
    score += _number_before(low, r"increased number of rare monsters") * 0.75
    quantity = re.search(r"item quantity:\s*\+?(\d+)%", low)
    gold = re.search(r"gold found:\s*\+?(\d+)%", low)
    if quantity:
        score += float(quantity.group(1)) * 0.55
    if gold:
        score += float(gold.group(1)) * 0.04
    return score


def chart_scope(chart: Chart):
    joined = normalize_text(" ".join(chart.modifiers))
    if "adjacent area" in joined or "adjacent chart" in joined:
        return "adjacent"
    if "all areas" in joined or "voyage" in joined:
        return "global"
    return "self"


def border_cell_scores(border_mods: Sequence[Sequence[str]]):
    result = []
    for cell in range(9):
        mods = border_mods[cell] if cell < len(border_mods) else ()
        score = 0.0
        for mod in mods:
            matched = match_catalog_entries(mod, ("border",))
            score += (
                sum(catalog_entry_score(entry) for entry in matched)
                if matched
                else _keyword_score(mod)
            )
        result.append(score)
    return result


def chart_position_score(
    chart: Chart,
    cell: int,
    border_mods: Sequence[Sequence[str]],
    border_scores: Sequence[float],
) -> float:
    text = " ".join(chart.modifiers)
    matched = match_catalog_entries(
        chart.raw_text or text,
        ("chart_self", "chart_adjacent", "chart_global"),
    )
    self_score = sum(
        catalog_entry_score(entry)
        for entry in matched
        if entry.get("scope") == "self"
    )
    adjacent_score = sum(
        catalog_entry_score(entry)
        for entry in matched
        if entry.get("scope") == "adjacent"
    )
    global_score = sum(
        catalog_entry_score(entry)
        for entry in matched
        if entry.get("scope") == "global"
    )
    adjacent_cells = tuple(neighbor for _, neighbor in cell_neighbors(cell))
    adjacent_count = len(adjacent_cells)
    fallback = _keyword_score(text)
    # Catalog scores represent the value in one affected Area. Adjacent
    # modifiers therefore benefit 2/3/4 Areas from corner/edge/center cells,
    # while global modifiers benefit the full nine-Area Voyage.
    base = (
        self_score
        + adjacent_score * adjacent_count
        + global_score * 9
        + fallback * 0.2
    )
    base += max(0, chart.area_level - 67) * 1.3
    if chart.area_level >= 83:
        base += 16

    own_border = border_scores[cell]
    neighbor_border = sum(border_scores[n] for n in adjacent_cells)
    low = normalize_text(text)
    score = base
    score += self_score * min(0.75, own_border / 220.0)
    score += adjacent_score * min(0.9, neighbor_border / 260.0)
    if adjacent_score:
        score += neighbor_border * 0.18
    if "rare monster" in low:
        score += neighbor_border * 0.42
    if "strongbox" in low:
        score += neighbor_border * 0.25

    own_border_text = normalize_text(" ".join(border_mods[cell]))
    if "divine orb" in own_border_text and (
        "rare monster" in low or "pack" in low or "quantity" in low
    ):
        score += 150
    if "stacked deck" in own_border_text and (
        "currency" in low or "pack" in low or "quantity" in low
    ):
        score += 110
    if "explicit modifier magnitude" in own_border_text:
        score += max(0.0, base) * 0.32
    for _, neighbor in cell_neighbors(cell):
        neighbor_text = normalize_text(" ".join(border_mods[neighbor]))
        if "adjacent" in low and border_scores[neighbor] > 40:
            score += 38
        if "divine orb" in neighbor_text and (
            "rare monster" in low or "pack" in low
        ):
            score += 72
    return score


def _best_shape_assignment(
    positions: Sequence[int],
    charts: Sequence[Chart],
    score_matrix: dict[tuple[int, str], float],
):
    if len(charts) < len(positions):
        return None
    ordered_positions = tuple(positions)
    candidates = tuple(charts)

    states = {0: (0.0, ())}
    for chart in candidates:
        next_states = dict(states)
        for mask, (score, chosen) in states.items():
            for pos_index, cell in enumerate(ordered_positions):
                bit = 1 << pos_index
                if mask & bit:
                    continue
                new_mask = mask | bit
                candidate = (
                    score + score_matrix[(cell, chart.uid)],
                    chosen + ((cell, chart),),
                )
                if new_mask not in next_states or candidate[0] > next_states[new_mask][0]:
                    next_states[new_mask] = candidate
        states = next_states
    return states.get((1 << len(ordered_positions)) - 1)


def _best_compatible_assignment(
    charts: Sequence[Chart],
    allowed_shapes: Sequence[set[str]],
    score_matrix: dict[tuple[int, str], float],
):
    states = {0: (0.0, ())}
    full_mask = (1 << len(allowed_shapes)) - 1
    for chart in charts:
        next_states = dict(states)
        for mask, (score, chosen) in states.items():
            for cell, shapes in enumerate(allowed_shapes):
                bit = 1 << cell
                if mask & bit or chart.shape not in shapes:
                    continue
                new_mask = mask | bit
                candidate = (
                    score + score_matrix[(cell, chart.uid)],
                    chosen + ((cell, chart),),
                )
                if (
                    new_mask not in next_states
                    or candidate[0] > next_states[new_mask][0]
                ):
                    next_states[new_mask] = candidate
        states = next_states
    return states.get(full_mask)


def plan_voyage(
    charts: Sequence[Chart],
    border_mods: Sequence[Sequence[str]] | None = None,
) -> VoyagePlan | None:
    border_mods = tuple(tuple(v) for v in (border_mods or [()] * 9))
    border_scores = border_cell_scores(border_mods)
    score_matrix = {
        (cell, chart.uid): chart_position_score(
            chart, cell, border_mods, border_scores
        )
        for cell in range(9)
        for chart in charts
    }

    best = None
    assignment_cache = {}
    for mask, edges, shapes in valid_topologies():
        orientation_options = tuple(
            {
                shape: compatible_orientations(shape, cell, edges[cell])
                for shape in BASE_EDGES
            }
            for cell in range(9)
        )
        allowed_shapes = tuple(
            {shape for shape, options in cell_options.items() if options}
            for cell_options in orientation_options
        )
        signature = tuple(tuple(sorted(value)) for value in allowed_shapes)
        assignment = assignment_cache.get(signature)
        if assignment is None:
            assignment = _best_compatible_assignment(
                charts, allowed_shapes, score_matrix
            )
            assignment_cache[signature] = assignment
        if assignment is None:
            continue
        total, selected = assignment
        selected_by_cell = dict(selected)
        for cell in range(9):
            connection_count = sum(edges[cell])
            for border_mod in border_mods[cell]:
                for entry in match_catalog_entries(border_mod, ("border",)):
                    total += _effects_score(entry.get("perConnEffects", ())) * connection_count
        if best is None or total > best[0]:
            best = (total, mask, edges, selected_by_cell)

    if best is None:
        return None

    total, mask, edges, selected_by_cell = best
    placements = []
    for cell in range(9):
        chart = selected_by_cell[cell]
        options = compatible_orientations(chart.shape, cell, edges[cell])
        actual_edges = min(
            options,
            key=lambda option: rotations_between(
                chart.initial_edges, option, chart.shape
            ),
        )
        rotations = rotations_between(
            chart.initial_edges, actual_edges, chart.shape
        )
        placements.append(
            Placement(
                cell=cell,
                chart=chart,
                required_edges=actual_edges,
                rotations=rotations,
                score=score_matrix[(cell, chart.uid)],
            )
        )
    notes = [
        f"Anchor cells: {', '.join(str(cell + 1) for cell in sorted(range(9), key=lambda c: border_scores[c], reverse=True)[:2])}",
        f"Charts considered: {len(charts)}",
        f"Known modifiers: {sum(len(modifier_catalog()[key]) for key in ('chart_self', 'chart_adjacent', 'chart_global', 'border'))}",
        f"Valid topologies evaluated: {len(valid_topologies())}",
    ]
    return VoyagePlan(placements=placements, score=total, edge_mask=mask, notes=notes)


def placement_order(plan: VoyagePlan, start: int = START_CELL):
    by_cell = {p.cell: p for p in plan.placements}
    order = []
    seen = {start}
    queue = [start]
    while queue:
        cell = queue.pop(0)
        order.append(by_cell[cell])
        for direction, other in cell_neighbors(cell):
            if by_cell[cell].required_edges[direction] and other not in seen:
                seen.add(other)
                queue.append(other)
    return order


def summarize_plan(plan: VoyagePlan) -> str:
    highlight_terms = (
        "divine",
        "stacked deck",
        "scarab",
        "currency",
        "rare monster",
        "pack size",
        "quantity",
        "strongbox",
        "lantern",
        "treasure",
    )

    def highlight(chart):
        selected = [
            re.sub(r"\s+", " ", modifier).strip()
            for modifier in chart.modifiers
            if any(term in normalize_text(modifier) for term in highlight_terms)
        ]
        return "; ".join(selected[:2]) or "no reward keyword"

    lines = [f"Voyage score: {plan.score:.1f}"]
    for placement in sorted(plan.placements, key=lambda p: p.cell):
        row, col = divmod(placement.cell, 3)
        lines.append(
            f"{row + 1},{col + 1}: {placement.chart.uid} "
            f"L{placement.chart.area_level} "
            f"{placement.chart.shape} R{placement.rotations} "
            f"({placement.score:.1f}) | {highlight(placement.chart)}"
        )
    lines.extend(plan.notes)
    return "\n".join(lines)
