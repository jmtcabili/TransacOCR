"""Preprocessing: EXIF rotation fix and resize. Returns a BGR array; never touches the file on disk."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 1600


def preprocess(path: str | Path, max_side: int = MAX_SIDE) -> np.ndarray:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        w, h = im.size
        longest = max(w, h)
        if longest > max_side:
            scale = max_side / longest
            im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        return np.asarray(im)[:, :, ::-1].copy()   # RGB -> BGR
