"""Extract wall polygons (filled paths) from a floor-plan frame of the permit sheet.

Walls in the plan are filled shapes:
  red  (1,0,0)        -> new concrete/block walls
  blue (0,0,1 / 0,.24,1) -> mamad (safe room) reinforced walls
  black (0,0,0)       -> existing walls (also picks up glyphs; filtered by size)

Outputs a debug PNG overlay and a JSON of polygons in plan points.
"""
import json
import sys
import pymupdf
from PIL import Image, ImageDraw

PDF = "plans/house_plans.pdf"
PAGE = 4

FRAMES = {
    "roof":      (1554, 789, 2227, 1533),
    "stairroom": (2254, 789, 2918, 1533),
    "first":     (2940, 789, 3610, 1533),
    "ground":    (3628, 789, 4393, 1640),
}

def color_class(fill):
    if fill is None:
        return None
    r, g, b = fill
    if r > 0.8 and g < 0.3 and b < 0.3:
        return "red"
    if b > 0.8 and r < 0.3:
        return "blue"
    if r < 0.15 and g < 0.15 and b < 0.15:
        return "black"
    if abs(r - 0.5) < 0.1 and abs(g - 0.5) < 0.1 and abs(b - 0.5) < 0.1:
        return "gray"
    return None

def path_polygons(d):
    """Convert a pymupdf drawing dict to a list of point loops."""
    loops = []
    cur = []
    for item in d["items"]:
        op = item[0]
        if op == "l":
            p1, p2 = item[1], item[2]
            if not cur:
                cur = [(p1.x, p1.y)]
            cur.append((p2.x, p2.y))
        elif op == "re":
            r = item[1]
            loops.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
        elif op == "qu":
            q = item[1]
            loops.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)])
        elif op == "c":
            # bezier - approximate with endpoints
            p1, p4 = item[1], item[4]
            if not cur:
                cur = [(p1.x, p1.y)]
            cur.append((p4.x, p4.y))
    if cur and len(cur) >= 3:
        loops.append(cur)
    return loops

def main():
    floor = sys.argv[1]
    fx0, fy0, fx1, fy1 = FRAMES[floor]
    doc = pymupdf.open(PDF)
    page = doc[PAGE]
    M = page.rotation_matrix

    polys = {"red": [], "blue": [], "black": [], "gray": []}
    for d in page.get_drawings():
        cls = color_class(d.get("fill"))
        if cls is None:
            continue
        r = pymupdf.Rect(d["rect"]) * M
        r.normalize()
        if not (fx0 <= r.x0 and r.x1 <= fx1 and fy0 <= r.y0 and r.y1 <= fy1):
            continue
        # filter tiny shapes (glyphs, symbols) for black; keep all red/blue
        if cls == "black" and (r.width < 2 and r.height < 2):
            continue
        for loop in path_polygons(d):
            pts = [pymupdf.Point(x, y) * M for x, y in loop]
            polys[cls].append([(round(p.x, 2), round(p.y, 2)) for p in pts])

    # strokes (thin lines / arcs) for opening validation: window glazing symbols, door arcs
    segs = []
    arcs = []
    for d in page.get_drawings():
        if d["type"] not in ("s", "fs"):
            continue
        r = pymupdf.Rect(d["rect"]) * M
        r.normalize()
        if not (fx0 <= r.x0 and r.x1 <= fx1 and fy0 <= r.y0 and r.y1 <= fy1):
            continue
        for item in d["items"]:
            if item[0] == "l":
                p1, p2 = item[1] * M, item[2] * M
                segs.append([round(p1.x, 2), round(p1.y, 2), round(p2.x, 2), round(p2.y, 2)])
            elif item[0] == "c":
                p1, p4 = item[1] * M, item[4] * M
                arcs.append([round(p1.x, 2), round(p1.y, 2), round(p4.x, 2), round(p4.y, 2)])

    # debug render: plan as background, polygons overlaid
    zoom = 4.0
    clip = pymupdf.Rect(fx0, fy0, fx1, fy1)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    colors = {"red": (255, 140, 0, 160), "blue": (0, 220, 220, 160), "black": (0, 200, 0, 160), "gray": (200, 0, 200, 120)}
    for cls, ps in polys.items():
        for poly in ps:
            pts = [((x - fx0) * zoom, (y - fy0) * zoom) for x, y in poly]
            if len(pts) >= 3:
                draw.polygon(pts, fill=colors[cls])
    img = Image.alpha_composite(img, ov)
    img.convert("RGB").save(f"plans/crops/walls_{floor}_debug.png")

    with open(f"plans/extracted_{floor}.json", "w") as f:
        json.dump({**polys, "segs": segs, "arcs": arcs}, f)
    print(floor, {k: len(v) for k, v in polys.items()}, "segs:", len(segs), "arcs:", len(arcs))

if __name__ == "__main__":
    main()
