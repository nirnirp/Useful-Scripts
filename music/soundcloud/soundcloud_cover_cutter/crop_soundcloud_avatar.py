# crop_soundcloud_avatar.py
# Usage:
#   python crop_soundcloud_avatar.py path/to/banner.jpg
# Outputs:
#   avatar_square.png  (exact square crop)
#   avatar_circle.png  (transparent PNG circle)

import sys, math
from PIL import Image, ImageDraw

if len(sys.argv) < 2:
    print("Usage: python crop_soundcloud_avatar.py path/to/banner.jpg")
    sys.exit(1)

BANNER_PATH = sys.argv[1]
OUT_SQUARE = "avatar_square.png"
OUT_CIRCLE = "avatar_circle.png"

# === Measurements copied from your console (_scMeasure) ===
MEASURE = {
    "recommended_square_crop_px": {
        "x": 57.3228346456693,
        "y": 47.0866141732283,
        "size": 405
    },
    "avatar_diameter_natural_px": 405
}

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

with Image.open(BANNER_PATH) as im:
    W, H = im.size

    # pull values and clamp to image bounds
    cx = MEASURE["recommended_square_crop_px"]["x"]
    cy = MEASURE["recommended_square_crop_px"]["y"]
    s  = MEASURE["recommended_square_crop_px"]["size"]

    x = clamp(cx, 0, W)
    y = clamp(cy, 0, H)
    s = min(s, W - x, H - y)

    # round to integer pixel box (keep alignment)
    left   = int(round(x))
    top    = int(round(y))
    right  = int(round(x + s))
    bottom = int(round(y + s))

    square = im.crop((left, top, right, bottom)).convert("RGBA")
    square.save(OUT_SQUARE)

    # circular avatar PNG (transparent corners)
    w, h = square.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, w-1, h-1), fill=255)

    circle = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    circle.paste(square, (0, 0), mask=mask)
    circle.save(OUT_CIRCLE)

    print(f"Saved {OUT_SQUARE} ({w}x{h}) and {OUT_CIRCLE} ({w}x{h})")
