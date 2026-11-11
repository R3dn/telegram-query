"""Telegram Query application icon generator.

Draws the app mark directly with Pillow (no SVG rasterizer dependency,
deterministic, CI-friendly) and emits:

  packaging/windows/assets/app.ico     multi-size Windows icon (16-256)
  packaging/windows/assets/app-256.png installer/UI master
  packaging/windows/assets/icon.svg    vector source of the same geometry

The mark: the classic folded paper plane (the archive's message heritage)
on a deep-ink rounded tile, with a query lens - the product in one glyph:
search your messages. Flat, high-contrast, legible at 16 px.

Geometry lives on a 256-unit grid; every size is redrawn crisply at that
size (4x supersampled) - never upscaled or blurred. The .ico embeds one
exact frame per size (Pillow skips sizes larger than the base image, so
the 256 px frame is passed as the base with the rest appended).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parents[1] / "assets"

# 256-grid palette
TILE = "#10141F"        # deep ink tile
PLANE = "#5B8DEF"       # brand indigo (upper sail)
PLANE_FOLD = "#3E6FC9"  # darker indigo (folded lower wing)
LENS = "#34B39A"        # discovery teal

# Paper plane on a 24 grid (lucide "send" silhouette):
#   nose N(22,2)  left tip L(2,9)  fold F(11,13)  tail T(15,22)
# Drawn as the two triangles that share the fold line N-F: the upper
# sail (N-L-F) and the darker lower wing (N-F-T).
_G = {
    "N": (22, 2),
    "L": (2, 9),
    "F": (11, 13),
    "T": (15, 22),
}

# 24-grid -> 256-grid mapping: glyph box (112 x 112 units) top-left
K = 5.6               # units per grid unit
BOX = (32.0, 30.0)    # glyph box origin on the 256 grid

LENS_C = (184.0, 184.0)
LENS_R = 32.0
LENS_STROKE = 14.0
LENS_HANDLE_END = (224.0, 224.0)


def _u(gx: float, gy: float) -> tuple[float, float]:
    """24-grid point -> 256-unit-grid point."""
    x, y = BOX
    return x + (gx - 2) * K, y + (gy - 2) * K


def _px(v: float, size: int) -> float:
    """256-grid units -> pixels at *size*."""
    return v * size / 256.0


def _pt(p: tuple[float, float], size: int) -> tuple[float, float]:
    return _px(p[0], size), _px(p[1], size)


def draw_icon(size: int) -> Image.Image:
    """Render the mark at *size* px (crisp redraw, no upscaling blur)."""
    s = 4  # supersample factor for smooth edges
    big = size * s
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # deep-ink rounded tile (radius ~22%, modern app-icon silhouette;
    # corners stay transparent for the .ico alpha)
    radius = _px(56, big)
    d.rounded_rectangle([0, 0, big - 1, big - 1], radius=radius, fill=TILE)

    # the paper plane: upper sail + darker folded wing share edge N-F
    sail = [_pt(_u(*_G[k]), big) for k in ("N", "L", "F")]
    wing = [_pt(_u(*_G[k]), big) for k in ("N", "F", "T")]
    d.polygon(sail, fill=PLANE)
    d.polygon(wing, fill=PLANE_FOLD)

    # the query lens, bottom-right: ring + 45-degree handle with round caps
    cx, cy = _pt(LENS_C, big)
    r, w = _px(LENS_R, big), max(1, int(_px(LENS_STROKE, big)))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=LENS, width=w)
    hx0, hy0 = cx + r * 0.7071, cy + r * 0.7071
    hx1, hy1 = _pt(LENS_HANDLE_END, big)
    d.line([hx0, hy0, hx1, hy1], fill=LENS, width=w)
    cap = w / 2
    d.ellipse([hx0 - cap, hy0 - cap, hx0 + cap, hy0 + cap], fill=LENS)
    d.ellipse([hx1 - cap, hy1 - cap, hx1 + cap, hy1 + cap], fill=LENS)

    return img.resize((size, size), Image.LANCZOS)


def svg() -> str:
    """Vector twin of the same geometry (hand-tunable source of truth)."""
    n, lt = _u(*_G["N"]), _u(*_G["L"])
    f, t = _u(*_G["F"]), _u(*_G["T"])
    poly = lambda pts: " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)  # noqa: E731
    cx, cy = LENS_C
    hx0, hy0 = cx + LENS_R * 0.7071, cy + LENS_R * 0.7071
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="56" fill="{TILE}"/>
  <polygon points="{poly([n, lt, f])}" fill="{PLANE}"/>
  <polygon points="{poly([n, f, t])}" fill="{PLANE_FOLD}"/>
  <circle cx="{cx:.0f}" cy="{cy:.0f}" r="{LENS_R:.0f}" fill="none"
          stroke="{LENS}" stroke-width="{LENS_STROKE:.0f}"/>
  <line x1="{hx0:.1f}" y1="{hy0:.1f}" x2="{LENS_HANDLE_END[0]:.0f}"
        y2="{LENS_HANDLE_END[1]:.0f}" stroke="{LENS}"
        stroke-width="{LENS_STROKE:.0f}" stroke-linecap="round"/>
</svg>
"""


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    sizes = [16, 20, 24, 32, 48, 64, 128, 256]
    frames = [draw_icon(s) for s in sizes]
    ico_path = ASSETS / "app.ico"
    # Pillow drops requested sizes larger than the base image, so the
    # 256 px frame must be the base; the exact-size frames are embedded
    # as-is (no resampling).
    frames[-1].save(
        ico_path, format="ICO",
        sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    draw_icon(256).save(ASSETS / "app-256.png")
    (ASSETS / "icon.svg").write_text(svg(), encoding="utf-8")

    # verify: the .ico must really contain one frame per size (direct
    # ICONDIR parse - Pillow's seek()/size do not expose every frame)
    import struct
    raw = ico_path.read_bytes()
    _res, _type, count = struct.unpack_from("<HHH", raw, 0)
    embedded: set[int] = set()
    for i in range(count):
        w, _h, *_ = struct.unpack_from("<BBBBHHII", raw, 6 + i * 16)
        embedded.add(w if w else 256)
    assert embedded == set(sizes), f"ico frames {embedded} != {sizes}"
    n_bytes = ico_path.stat().st_size
    assert n_bytes > 8_000, f"ico suspiciously small: {n_bytes} bytes"
    print(f"wrote {ico_path} ({n_bytes} bytes, frames {sorted(embedded)}), "
          f"app-256.png, icon.svg")


if __name__ == "__main__":
    main()
