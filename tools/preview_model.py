"""Render top-down previews of house.json: per-floor and combined."""
import json
from PIL import Image, ImageDraw

m = json.load(open("viewer/house.json"))
S = 70
W, H = 14, 18

def xy(p):
    return (int((p[0] + 2) * S), int((H - 3 - p[1]) * S))

# combined overlay
img = Image.new("RGB", (int(W * S), int(H * S)), "white")
d = ImageDraw.Draw(img, "RGBA")
colors = {"ground": (200, 0, 0, 140), "first": (0, 100, 255, 120), "stairroom": (0, 180, 0, 150)}
for name, fl in m["floors"].items():
    for sl in fl["footprint"]:
        d.polygon([xy(p) for p in sl["outer"]], outline=colors[name], width=2)
    for w in fl["walls"]:
        d.polygon([xy(p) for p in w["outer"]], fill=colors[name])
img.save("plans/crops/model_preview.png")

# per floor with openings
for name, fl in m["floors"].items():
    img = Image.new("RGB", (int(W * S), int(H * S)), "white")
    d = ImageDraw.Draw(img, "RGBA")
    for sl in fl["footprint"]:
        d.polygon([xy(p) for p in sl["outer"]], outline=(150, 150, 150, 255), width=2)
    for w in fl["walls"]:
        d.polygon([xy(p) for p in w["outer"]], fill=(60, 60, 60, 230))
        for h in w["holes"]:
            d.polygon([xy(p) for p in h], fill=(255, 255, 255, 255))
    for o in fl["openings"]:
        x0, y0, x1, y1 = o["rect"]
        c = (0, 200, 0, 180) if o["exterior"] else (255, 150, 0, 200)
        d.rectangle([xy((x0, y1)), xy((x1, y0))], fill=c)
    img.save(f"plans/crops/model_{name}.png")
print("ok")
