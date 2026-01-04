#!/usr/bin/env python3
"""
prep_sprites.py

Easy CLI:
  python prep_sprites.py image.png

If --input is a filename (not a full path),
it is assumed to live in DEFAULT_INPUT_DIR.
"""

import argparse
import os
import numpy as np
import cv2
from PIL import Image

# =========================
# Paths (EDIT ONCE)
# =========================

DEFAULT_INPUT_DIR = r"C:\Users\User\Documents\Code\290825\040126\platformer_game\assets\images"
DEFAULT_OUTDIR = r"C:\Users\User\Documents\Code\290825\040126\platformer_game\assets\images\sprites\player"


# =========================
# Utility
# =========================

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def resolve_input_path(input_arg: str) -> str:
    """
    If input is just a filename, prepend DEFAULT_INPUT_DIR.
    If it's already a full path, leave it alone.
    """
    if os.path.isabs(input_arg):
        return input_arg
    return os.path.join(DEFAULT_INPUT_DIR, input_arg)

def pil_to_bgra(img):
    return cv2.cvtColor(np.array(img.convert("RGBA")), cv2.COLOR_RGBA2BGRA)

def bgra_to_pil(arr):
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGRA2RGBA), "RGBA")


# =========================
# Core processing
# =========================

def split_three_panels(img):
    h, w = img.shape[:2]
    pw = w // 3
    return img[:, :pw], img[:, pw:2*pw], img[:, 2*pw:]

def foreground_mask(bgra, white_thresh=240):
    b, g, r, _ = cv2.split(bgra)
    bg = (r >= white_thresh) & (g >= white_thresh) & (b >= white_thresh)
    mask = (~bg).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)

def edge_mask(bgra):
    gray = cv2.cvtColor(bgra[:, :, :3], cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    return cv2.dilate(edges, None, iterations=1)

def crop_to_subject(mask, margin=6):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    x, y, w, h = cv2.boundingRect(max(cnts, key=cv2.contourArea))
    return max(0, x-margin), max(0, y-margin), x+w+margin, y+h+margin

def process_panel(panel, name, outdir):
    fg = foreground_mask(panel)
    edges = edge_mask(panel)
    combined = cv2.bitwise_or(fg, edges)

    bbox = crop_to_subject(combined)
    if bbox is None:
        print(f"⚠️ No subject detected in {name}")
        return

    x0, y0, x1, y1 = bbox
    crop = panel[y0:y1, x0:x1].copy()
    crop[:, :, 3] = combined[y0:y1, x0:x1]

    out_path = os.path.join(outdir, f"{name}.png")
    bgra_to_pil(crop).save(out_path)
    print(f"✅ {name}.png written")


# =========================
# Main
# =========================

def main():
    ap = argparse.ArgumentParser(description="Prepare front/back/side sprites")
    ap.add_argument(
        "input",
        help="Input image filename or full path"
    )
    ap.add_argument(
        "--outdir",
        default=DEFAULT_OUTDIR,
        help="Output directory (default: player sprites folder)"
    )
    args = ap.parse_args()

    input_path = resolve_input_path(args.input)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input image not found:\n{input_path}")

    ensure_dir(args.outdir)

    sheet = pil_to_bgra(Image.open(input_path))
    front, side, back = split_three_panels(sheet)


    process_panel(front, "front", args.outdir)
    process_panel(back, "back", args.outdir)
    process_panel(side, "side", args.outdir)

    print("🎮 Sprites ready")

if __name__ == "__main__":
    main()
