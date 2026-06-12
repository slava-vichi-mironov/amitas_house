"""Build a 3D house model (viewer/house.json) from extracted wall polygons.

Pipeline:
  1. Load wall polygons (red = walls, blue = mamad) per floor, filtered to house cluster.
  2. Union into clean wall components.
  3. Align floors using the section-axis markers / verified offsets.
  4. Convert to meters (1:100 plan -> 1 pt = 0.035278 m), y-up, origin at SW house corner.
  5. Detect openings (gaps in walls): exterior -> windows/glazing, interior -> doors.
  6. Slabs: floor n+1 slab = closed footprint of floor n. Parapets on exposed slab edges.
  7. Stairs: U-flights inside the stair core.
"""
import json
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, box, LineString
from shapely.ops import unary_union
from shapely import affinity

# Calibrated against the 860cm dimension chain on the ground-floor north facade
# (dimension arrows at x=3976.7 and x=4185.9 rendered pts -> 209.2 pt = 8.60 m).
SCALE = 8.60 / 209.2  # meters per pdf point

FLOORS = ["ground", "first", "stairroom"]
SRC = {
    "ground":    ("plans/extracted_ground.json",    (3900, 880, 4330, 1420)),
    "first":     ("plans/extracted_first.json",     (3170, 880, 3640, 1420)),
    "stairroom": ("plans/extracted_stairroom.json", (2480, 880, 2950, 1420)),
}
# verified: dy via section-axis letters (exact), dx via west-wall + stair-core overlay check
OFFSETS = {"ground": (0.0, 0.0), "first": (746.00, 3.16), "stairroom": (1434.81, 9.67)}

LEVELS = {
    "ground":    {"z": 0.00, "top": 3.38},
    "first":     {"z": 3.38, "top": 6.78},
    "stairroom": {"z": 6.78, "top": 9.20},
}
PARAPET_H = 1.12
PARAPET_T = 0.12
WALL_T = 0.22          # exterior wall thickness for the continuous shell


def load_walls(name):
    path, bbox = SRC[name]
    d = json.load(open(path))
    bx = box(*bbox)
    dx, dy = OFFSETS[name]
    polys = []
    for cls in ("red", "blue"):
        for loop in d[cls]:
            if len(loop) < 3:
                continue
            p = Polygon(loop)
            if not p.is_valid:
                p = p.buffer(0)
            if p.is_empty or p.area < 0.5:
                continue
            r = p.bounds
            if r[2] - r[0] > 350 or r[3] - r[1] > 350:
                continue
            if not bx.contains(p.centroid):
                continue
            polys.append(affinity.translate(p, dx, dy))
    u = unary_union(polys)
    return u if isinstance(u, MultiPolygon) else MultiPolygon([u])


def load_strokes(name, origin):
    """Stroke segments and bezier chords in meters (for opening validation)."""
    path, bbox = SRC[name]
    d = json.load(open(path))
    bx = box(*bbox)
    dx, dy = OFFSETS[name]
    ox, oy = origin
    segs = []
    for x0, y0, x1, y1 in d.get("segs", []):
        if not (bbox[0] - 20 < x0 < bbox[2] + 20 and bbox[1] - 20 < y0 < bbox[3] + 20):
            continue
        segs.append(((x0 + dx - ox) * SCALE, (oy - (y0 + dy)) * SCALE,
                     (x1 + dx - ox) * SCALE, (oy - (y1 + dy)) * SCALE))
    arcs = []
    for x0, y0, x1, y1 in d.get("arcs", []):
        if not (bbox[0] - 20 < x0 < bbox[2] + 20 and bbox[1] - 20 < y0 < bbox[3] + 20):
            continue
        arcs.append(((x0 + dx - ox) * SCALE, (oy - (y0 + dy)) * SCALE,
                     (x1 + dx - ox) * SCALE, (oy - (y1 + dy)) * SCALE))
    return segs, arcs


def to_meters(mp, origin):
    ox, oy = origin
    out = []
    geoms = mp.geoms if hasattr(mp, "geoms") else [mp]
    for g in geoms:
        if g.is_empty:
            continue
        ext = [((x - ox) * SCALE, (oy - y) * SCALE) for x, y in g.exterior.coords]
        ints = [[((x - ox) * SCALE, (oy - y) * SCALE) for x, y in h.coords] for h in g.interiors]
        q = Polygon(ext, ints)
        if not q.is_valid:
            q = q.buffer(0)
        if isinstance(q, Polygon):
            out.append(q)
        else:
            out.extend([gg for gg in q.geoms])
    return MultiPolygon(out)


def wall_endcaps(walls_m, max_cap=0.42):
    """Short segments of wall polygons = wall end caps at openings.
    Returns list of (mid, axis_dir, outward_normal, length)."""
    caps = []
    geoms = walls_m.geoms if hasattr(walls_m, "geoms") else [walls_m]
    for g in geoms:
        ring = list(g.exterior.coords)
        n = len(ring) - 1
        for i in range(n):
            (x0, y0), (x1, y1) = ring[i], ring[i + 1]
            dx, dy = x1 - x0, y1 - y0
            L = (dx * dx + dy * dy) ** 0.5
            if L < 0.05 or L > max_cap:
                continue
            if abs(dx) > 0.02 and abs(dy) > 0.02:
                continue  # only axis-aligned caps
            mid = ((x0 + x1) / 2, (y0 + y1) / 2)
            # shapely exterior is CCW; for y-up coords outward normal of CCW ring is right of direction
            nx, ny = dy / L, -dx / L
            # ensure normal points away from wall body
            probe = (mid[0] + nx * 0.06, mid[1] + ny * 0.06)
            from shapely.geometry import Point
            if g.contains(Point(probe)):
                nx, ny = -nx, -ny
            caps.append((mid, (abs(ny), abs(nx)), (nx, ny), L))
    return caps


def pair_openings(walls_m, min_gap=0.45, max_gap=4.6):
    """Pair facing end caps into opening rectangles."""
    caps = wall_endcaps(walls_m)
    used = set()
    rects = []
    for i, (m1, ax1, n1, L1) in enumerate(caps):
        best = None
        for j, (m2, ax2, n2, L2) in enumerate(caps):
            if j == i or j in used or i in used:
                continue
            # normals must oppose
            if n1[0] * n2[0] + n1[1] * n2[1] > -0.9:
                continue
            vx, vy = m2[0] - m1[0], m2[1] - m1[1]
            d_along = vx * n1[0] + vy * n1[1]
            d_perp = abs(vx * n1[1] - vy * n1[0])
            if d_along < min_gap or d_along > max_gap or d_perp > 0.16:
                continue
            if abs(L1 - L2) > 0.25:
                continue
            if best is None or d_along < best[0]:
                best = (d_along, j)
        if best is not None:
            j = best[1]
            m2, _, _, L2 = caps[j][0], caps[j][1], caps[j][2], caps[j][3]
            w = (L1 + L2) / 2
            # build rect between caps
            cx0 = min(m1[0], m2[0]) if abs(n1[0]) > 0.5 else m1[0] - w / 2
            cx1 = max(m1[0], m2[0]) if abs(n1[0]) > 0.5 else m1[0] + w / 2
            cy0 = min(m1[1], m2[1]) if abs(n1[1]) > 0.5 else m1[1] - w / 2
            cy1 = max(m1[1], m2[1]) if abs(n1[1]) > 0.5 else m1[1] + w / 2
            # opening must not cross other walls
            probe = box(cx0, cy0, cx1, cy1).buffer(-0.03, join_style=2)
            if not probe.is_empty and probe.intersection(walls_m).area > 0.25 * probe.area:
                continue
            used.add(i)
            used.add(j)
            rects.append({"rect": [round(cx0, 3), round(cy0, 3), round(cx1, 3), round(cy1, 3)],
                          "thick": round(w, 3),
                          "span": round(best[0], 2)})
    # non-max suppression of overlapping rects
    rects.sort(key=lambda r: (r["rect"][2] - r["rect"][0]) * (r["rect"][3] - r["rect"][1]))
    kept = []
    for r in rects:
        b = box(*r["rect"])
        if any(b.intersection(box(*k["rect"])).area > 0.4 * b.area for k in kept):
            continue
        kept.append(r)
    return kept


def _glaze_in_opening(segs, walls_m, b, horiz, span):
    """Glazing symbols are drawn in wall gaps, adjacent to wall fills."""
    from shapely.geometry import Point
    best = 0.0
    for sx0, sy0, sx1, sy1 in segs:
        mx, my = (sx0 + sx1) / 2, (sy0 + sy1) / 2
        pt = Point(mx, my)
        if not b.contains(pt):
            continue
        # in the opening, not on a distant dimension chain (parking, site)
        if walls_m.distance(pt) > 0.38:
            continue
        dx, dy = abs(sx1 - sx0), abs(sy1 - sy0)
        L = (dx * dx + dy * dy) ** 0.5
        if L < 0.25:
            continue
        if (horiz and dx > 3 * dy) or (not horiz and dy > 3 * dx):
            best = max(best, L)
    return best


def validate_openings(openings, segs, arcs, walls_m):
    """Keep openings with wall-adjacent glazing symbols or door arcs.

    Glazing strokes far from walls (parking dimension chains) are ignored.
    """
    from shapely.geometry import Point
    shell = walls_m.convex_hull.buffer(0.8)
    # rough interior: area inside the wall ring
    inner = walls_m.buffer(0.15, join_style=2).buffer(-1.6, join_style=2)
    out = []
    for o in openings:
        x0, y0, x1, y1 = o["rect"]
        w, h = x1 - x0, y1 - y0
        horiz = w >= h
        b = box(x0 - 0.04, y0 - 0.04, x1 + 0.04, y1 + 0.04)
        span = max(w, h)
        center = Point((x0 + x1) / 2, (y0 + y1) / 2)
        if not shell.contains(center):
            continue
        glaze = _glaze_in_opening(segs, walls_m, b, horiz, span)
        has_arc = any(
            b.contains(Point((ax0 + ax1) / 2, (ay0 + ay1) / 2))
            and walls_m.distance(Point((ax0 + ax1) / 2, (ay0 + ay1) / 2)) <= 0.38
            and 0.25 < ((ax1 - ax0) ** 2 + (ay1 - ay0) ** 2) ** 0.5 < 1.6
            for ax0, ay0, ax1, ay1 in arcs
        )
        is_interior = inner.contains(center)
        if is_interior:
            if has_arc or 0.50 <= span <= 1.35 or glaze >= 0.35 * span:
                o["sym"] = "arc" if has_arc else "gap"
                out.append(o)
            continue
        if glaze >= 0.45 * span or has_arc:
            o["sym"] = "arc" if has_arc and glaze < 0.45 * span else "glaze"
            out.append(o)
    return out


def closed_footprint(walls_m, openings):
    """Walls + opening fillers -> outer shells."""
    fillers = [box(*o["rect"]).buffer(0.02, join_style=2) for o in openings]
    u = unary_union([walls_m.buffer(0.02, join_style=2)] + fillers)
    # close remaining small touches
    u = u.buffer(0.12, join_style=2).buffer(-0.14, join_style=2)
    if isinstance(u, Polygon):
        u = MultiPolygon([u])
    shells = [Polygon(g.exterior) for g in u.geoms if g.area > 2]
    return unary_union(shells)


def classify_openings(openings, walls_m, footprint, floor):
    """Mark openings exterior/interior; assign kind and sill/head heights."""
    inner = footprint.buffer(-0.45, join_style=2)
    for o in openings:
        b = box(*o["rect"])
        o["exterior"] = not inner.contains(b)
        sill_strip = b.intersection(walls_m).area > 0.10 * b.area
        if not o["exterior"]:
            o["kind"] = "door"
            o["sill"], o["head"] = 0.0, 2.10
        elif o.get("sym") == "arc" or (o["span"] <= 1.05 and not sill_strip):
            o["kind"] = "entry"
            o["sill"], o["head"] = 0.0, 2.40
        elif o["span"] >= 1.45 and not sill_strip:
            o["kind"] = "glazing"          # patio sliding doors
            o["sill"], o["head"] = 0.02, 2.40
        else:
            o["kind"] = "window"           # o.k.=240 -> sill +110
            o["sill"], o["head"] = 1.10, 2.40
    return openings


def merge_walls(walls_m, openings, eps=0.07):
    """Fuse fragmented wall polygons and cut 2D opening footprints (vertical voids when extruded)."""
    geoms = list(walls_m.geoms) if hasattr(walls_m, "geoms") else [walls_m]
    if not geoms:
        return walls_m
    merged = unary_union([p.buffer(eps, join_style=2) for p in geoms])
    merged = merged.buffer(-eps * 0.88, join_style=2)
    if openings:
        cuts = unary_union([box(*o["rect"]).buffer(0.025, join_style=2) for o in openings])
        merged = merged.difference(cuts)
    if merged.is_empty:
        return walls_m
    if isinstance(merged, Polygon):
        merged = MultiPolygon([merged])
    return merged


def poly_dicts(mp):
    res = []
    geoms = mp.geoms if hasattr(mp, "geoms") else [mp]
    for g in geoms:
        if g.is_empty or g.area < 0.01:
            continue
        if not g.is_valid:
            g = g.buffer(0)
        res.append({
            "outer": [[round(x, 3), round(y, 3)] for x, y in g.exterior.coords],
            "holes": [[[round(x, 3), round(y, 3)] for x, y in h.coords] for h in g.interiors],
        })
    return res


def parapet_segments(slab, walls_above):
    """Slab boundary edges not covered by walls above -> parapets."""
    segs = []
    geoms = slab.geoms if hasattr(slab, "geoms") else [slab]
    wa = walls_above.buffer(0.18) if walls_above is not None else None
    for g in geoms:
        bnd = g.exterior
        n = len(bnd.coords)
        for i in range(n - 1):
            seg = LineString([bnd.coords[i], bnd.coords[i + 1]])
            if seg.length < 0.25:
                continue
            if wa is not None and wa.contains(seg):
                continue
            if wa is not None and seg.intersection(wa).length > seg.length * 0.7:
                continue
            segs.append([[round(c, 3) for c in seg.coords[0]],
                         [round(c, 3) for c in seg.coords[1]]])
    return segs


def main():
    walls_pts = {f: load_walls(f) for f in FLOORS}
    gb = walls_pts["ground"].bounds
    origin = (gb[0], gb[3])

    walls_m = {f: to_meters(walls_pts[f], origin) for f in FLOORS}
    opens = {}
    for f in FLOORS:
        cand = pair_openings(walls_m[f])
        segs, arcs = load_strokes(f, origin)
        opens[f] = validate_openings(cand, segs, arcs, walls_m[f])
        print(f, "candidates:", len(cand), "validated:", len(opens[f]))
    feet = {f: closed_footprint(walls_m[f], opens[f]) for f in FLOORS}

    model = {"meta": {"scale": SCALE, "parapet_h": PARAPET_H, "parapet_t": PARAPET_T},
             "floors": {}, "stairs": [], "site": {}}

    slab_above = {"ground": "first", "first": "stairroom", "stairroom": None}

    for f in FLOORS:
        lv = LEVELS[f]
        openings = classify_openings(opens[f], walls_m[f], feet[f], f)
        merged = merge_walls(walls_m[f], openings)
        # continuous watertight exterior shell from the clean footprint ring.
        # Inset 5 mm so fragmented walls win on faces they cover; shell fills slits.
        foot = feet[f]
        ring = foot.buffer(-0.005, join_style=2).difference(foot.buffer(-WALL_T, join_style=2))
        ext_cuts = [box(*o["rect"]) for o in openings if o["exterior"]]
        if ext_cuts:
            ring = ring.difference(unary_union([c.buffer(0.04, join_style=2) for c in ext_cuts]))
        if isinstance(ring, Polygon):
            ring = MultiPolygon([ring])
        model["floors"][f] = {
            "z": lv["z"], "top": lv["top"],
            "walls": poly_dicts(merged),
            "shell": poly_dicts(ring),
            "footprint": poly_dicts(feet[f]),
            "openings": openings,
        }
        print(f, "walls:", len(model["floors"][f]["walls"]),
              f"(merged from {len(walls_m[f].geoms)})",
              "shell:", len(model["floors"][f]["shell"]),
              "openings:", len(openings),
              "ext:", sum(1 for o in openings if o["exterior"]))

    # terraces / roof slabs with parapets
    # slab over floor f sits at LEVELS[f]['top']; exposed part = footprint(f) - footprint(above)
    model["slabs"] = []
    for f in FLOORS:
        above = slab_above[f]
        slab = feet[f]
        z = LEVELS[f]["top"]
        walls_above = walls_m[above] if above else None
        exposed = slab.difference(feet[above]) if above else slab
        model["slabs"].append({
            "z": z, "thick": 0.25,
            "poly": poly_dicts(slab),
            "parapets": parapet_segments(slab, walls_above),
        })
        print("slab at", z, "parapet segs:", len(model["slabs"][-1]["parapets"]))

    # ground slab
    model["slabs"].append({"z": 0.0, "thick": 0.20, "poly": poly_dicts(feet["ground"]), "parapets": []})

    # stair core (meters): from stairroom walls bounds (same shaft on all floors;
    # plan shows U-stairs, runs 9x28, risers 1-19 then 20-40)
    sb = walls_m["stairroom"].bounds
    model["stairs"] = [
        {"z0": 0.0, "z1": 3.38, "core": [round(v, 3) for v in sb], "risers": 19},
        {"z0": 3.38, "z1": 6.78, "core": [round(v, 3) for v in sb], "risers": 20},
    ]

    # site footprint for context
    model["site"] = {"lot": [[-8, -7], [18, -7], [18, 20], [-8, 20]]}

    with open("viewer/house.json", "w") as fjson:
        json.dump(model, fjson)
    print("wrote viewer/house.json")
    print("house bounds (m):", [round(v, 2) for v in feet["ground"].bounds])


if __name__ == "__main__":
    main()
