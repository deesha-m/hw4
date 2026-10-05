"""Give every product photo the same background and framing.

The catalogue photos come on solid black, solid white, or white with black side bars.
This script finds the background by flood-filling inward from the image edges
(so dark parts of a navy garment are never touched), replaces it with one warm stone
color, softens the cut edge, and re-centers each garment on a same-size square.

Originals in data/products/ are left untouched; results go to data/products_clean/.

Run from the homework/4 folder:
    .venv/bin/python scripts/clean_product_images.py
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "products"
OUTPUT = ROOT / "data" / "products_clean"

BACKGROUND = (243, 239, 232)  # warm stone, matches --mount in frontend/src/index.css
CANVAS = 900                  # every output is 900 x 900
FILL = 0.86                   # garment takes up to 86% of the canvas
BLACK_MAX = 16                # a pixel is "black background" if all channels are below this
WHITE_FLOOR = 236             # ...or "white background" if all channels are above a per-image cutoff (never below this)
RING_INSET = 8                # also seed from a ring this many pixels in from the edge
HOLE_MAX = 8                  # enclosed backdrop gaps (e.g. between sleeve and body) are almost pure black...
HOLE_MIN_AREA = 300           # ...and large; the darkest garment shadows never form a patch this big
HOLE_FRINGE = 30              # a gap's soft JPEG fringe is a little brighter; navy fabric stays above this
HOLE_SIDE = 0.2               # ...and off-center (logos sit in the middle 40% of the garment; arm gaps don't)


def background_mask(rgb: np.ndarray) -> np.ndarray:
    """True where a pixel is background: near-black or near-white AND connected to the edge,
    plus large pure-black gaps enclosed by the garment."""
    # White backdrops range from pure 255 to about 241. The cutoff sits just under this photo's
    # own backdrop, so a white garment on pure white (e.g. the Yale Bowl tee) isn't erased.
    # Sample the outer edge and a ring a few pixels in, since a few photos have a thin black
    # frame around a white backdrop.
    i = RING_INSET
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).min(axis=1)
    ring = np.concatenate([rgb[i, i:-i], rgb[-1 - i, i:-i], rgb[i:-i, i], rgb[i:-i, -1 - i]]).min(axis=1)
    white_border = np.concatenate([border, ring])
    white_border = white_border[white_border > 200]
    white_min = max(WHITE_FLOOR, np.percentile(white_border, 1) - 3) if len(white_border) else 255
    candidate = (rgb.max(axis=2) < BLACK_MAX) | (rgb.min(axis=2) > white_min)
    seed = np.zeros_like(candidate)
    seed[0, :], seed[-1, :], seed[:, 0], seed[:, -1] = (
        candidate[0, :], candidate[-1, :], candidate[:, 0], candidate[:, -1]
    )
    seed[i, i:-i] |= candidate[i, i:-i]
    seed[-1 - i, i:-i] |= candidate[-1 - i, i:-i]
    seed[i:-i, i] |= candidate[i:-i, i]
    seed[i:-i, -1 - i] |= candidate[i:-i, -1 - i]
    mask = _grow(seed, candidate)
    # Black backdrop can also show through gaps the garment encloses (between an arm and the
    # body), which the edge fill can't reach. Only for black backdrops, and only off-center
    # gaps: black or white shapes in the middle of a garment are usually its logo.
    black_backdrop = (border < BLACK_MAX).mean() > 0.5
    if black_backdrop:
        cols = np.nonzero((~mask).any(axis=0))[0]
        center, width = (cols[0] + cols[-1]) / 2, cols[-1] - cols[0] + 1
        holes = _large_regions(
            (rgb.max(axis=2) < HOLE_MAX) & ~mask,
            HOLE_MIN_AREA,
            keep=lambda xs: abs(np.mean(xs) - center) > HOLE_SIDE * width,
        )
        if holes.any():
            mask |= _grow(holes, rgb.max(axis=2) < HOLE_FRINGE)
    return mask


def _grow(seed: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """Grow the seed through connected `allowed` pixels until nothing changes."""
    mask = seed & allowed
    while True:
        grown = mask.copy()
        grown[1:, :] |= mask[:-1, :]
        grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        grown &= allowed
        if (grown == mask).all():
            return mask
        mask = grown


def _large_regions(mask: np.ndarray, min_area: int, keep=lambda xs: True) -> np.ndarray:
    """Connected regions of `mask` with at least `min_area` pixels whose x-coordinates pass `keep`."""
    out = np.zeros_like(mask)
    seen = np.zeros_like(mask)
    h, w = mask.shape
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        seen[y, x] = True
        stack, region = [(y, x)], []
        while stack:
            cy, cx = stack.pop()
            region.append((cy, cx))
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(region) >= min_area:
            ys, xs = zip(*region)
            if keep(xs):
                out[list(ys), list(xs)] = True
    return out


def clean(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    rgb = np.asarray(image).astype(np.int16)
    bg = background_mask(rgb)

    # Alpha: 255 for garment, 0 for background, with a soft 1-2 px edge. Growing the
    # background by one pixel first trims the dark anti-aliased fringe left by black backdrops.
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))

    cut = image.copy()
    cut.putalpha(alpha)
    box = alpha.point(lambda a: 255 if a > 40 else 0).getbbox() or (0, 0, *image.size)
    garment = cut.crop(box)

    scale = min(CANVAS * FILL / garment.width, CANVAS * FILL / garment.height)
    garment = garment.resize((round(garment.width * scale), round(garment.height * scale)), Image.LANCZOS)

    canvas = Image.new("RGB", (CANVAS, CANVAS), BACKGROUND)
    offset = ((CANVAS - garment.width) // 2, (CANVAS - garment.height) // 2)
    canvas.paste(garment, offset, garment)
    return canvas


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    files = sorted(p for p in SOURCE.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    for path in files:
        clean(path).save(OUTPUT / f"{path.stem}.jpg", quality=90, optimize=True)
    print(f"Cleaned {len(files)} images -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
