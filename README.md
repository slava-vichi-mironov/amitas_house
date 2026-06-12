# Amita's House — 3D from permit plans

Interactive 3D model of the Imbarman family house (permit **20230022**), generated from the Hebrew architectural PDF (גרמושקה).

## Quick start

```bash
# 1. Install Python deps (uv)
uv sync

# 2. Install viewer deps
npm install

# 3. Place the plan PDF (if not already present)
#    plans/house_plans.pdf

# 4. Extract geometry + build model
npm run build
# or: uv run python tools/rebuild_all.py

# 5. Open the viewer
npm run serve
# → http://localhost:8742/viewer/index.html
```

## Viewer controls

| Mode | Controls |
|------|----------|
| **Orbit** | Drag to rotate, scroll to zoom, right-drag to pan |
| **Walk inside** | Click canvas, then **WASD** move, mouse look |
| | **E / Q** — go up / down a floor |
| | **Shift** — run |
| | **Esc** — release mouse |

Use the panel checkboxes to hide floors and peek inside.

## Pipeline

```
plans/house_plans.pdf
        │
        ▼
tools/extract_walls.py     ← wall polygons (red/blue fills) + strokes per floor
        │
        ▼
plans/extracted_{floor}.json
        │
        ▼
tools/build_model.py       ← align floors, detect openings, slabs, stairs
        │
        ▼
viewer/house.json          ← consumed by Three.js viewer
```

### Floors modeled

| Floor | Level (m) | Contents |
|-------|-----------|----------|
| Ground | ±0.00 → 3.38 | Living, kitchen, mamad, entrance, stairs |
| First | 3.38 → 6.78 | Bedrooms, bathrooms, balcony |
| Stair room | 6.78 → 9.20 | Stair shaft to roof |

Scale is calibrated from the **860 cm** dimension chain on the ground-floor north facade.

## Debug / validation

```bash
# Top-down model preview (PNG)
uv run python tools/preview_model.py
# → plans/crops/model_ground.png, model_first.png, …

# Openings overlaid on original plan drawings
uv run python tools/check_openings.py
# → plans/crops/openings_ground.png, …

# Crop a region of the PDF at high zoom
uv run python tools/crop.py PAGE X0 Y0 X1 Y1 ZOOM OUT.png
# coordinates are fractions 0..1 of the rendered page
```

## Project layout

```
plans/           PDF + extracted JSON + debug crops
tools/           Python extraction & build scripts
viewer/          Three.js web app (index.html, main.js, house.json)
```

## Limitations

- Openings are detected from wall-gap geometry + glazing symbols; some may be missing or misclassified.
- Roof is slabs + parapets only (no pitched roof geometry).
- Site, parking, and landscaping are simplified.
- Mamad (safe room) walls are not separately materialized yet.

## Deploy (free public URL)

### One command — GitHub Pages (recommended)

Prerequisites: [GitHub CLI](https://cli.github.com/) (`brew install gh && gh auth login`).

```bash
npm run deploy
```

This will:

1. Rebuild `viewer/house.json` from the local PDF
2. Create a GitHub repo if needed (`gh repo create`)
3. Commit and push (the PDF is **never** included — see `.gitignore`)
4. Trigger [`.github/workflows/pages.yml`](.github/workflows/pages.yml) → live at:

   **`https://<your-username>.github.io/<repo-name>/`**

First time only: open the repo on GitHub → **Settings → Pages → Build and deployment → Source: GitHub Actions**.

### Manual / no GitHub

The viewer is three static files (`viewer/index.html`, `main.js`, `house.json`). Three.js loads from jsDelivr.

**Netlify Drop:** zip `viewer/`, drop at [app.netlify.com/drop](https://app.netlify.com/drop).

| Service | URL pattern |
|---------|-------------|
| GitHub Pages | `*.github.io` |
| Cloudflare Pages | `*.pages.dev` |
| Netlify | `*.netlify.app` |

**Privacy:** `plans/house_plans.pdf` stays local. `house.json` still describes your floor plan — only publish if you're comfortable with that.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.12+)
- Node.js 18+ (optional — only needed if you prefer local Three.js)
