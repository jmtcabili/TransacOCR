"""Hybrid recogniser (exp3): RapidOCR finds text boxes, rows are merged, each row is cropped and read
by glm-ocr through Ollama. RECOGNISER=rapid skips glm-ocr and uses RapidOCR's own text.

`read()` returns items shaped {text, box (0-1000 of the image), rapid}, top to bottom.
"""
import logging
from typing import Callable

import cv2
import numpy as np

log = logging.getLogger(__name__)

GLM_MODEL = "glm-ocr:q8_0"


class OcrError(Exception):
    """The image could not be read at all (detection failed)."""


def merge_rows(dets: list[dict], tol: float = 0.5) -> list[dict]:
    """Merge boxes whose vertical centre is within tol * height of a row's first box."""
    rows = []
    for d in sorted(dets, key=lambda d: (d["box"][1] + d["box"][3]) / 2):
        yc = (d["box"][1] + d["box"][3]) / 2
        h = d["box"][3] - d["box"][1]
        for r in reversed(rows[-2:]):   # only the latest rows can match
            if abs(yc - r["yc0"]) <= tol * max(h, r["h0"]):
                r["members"].append(d)
                break
        else:
            rows.append({"yc0": yc, "h0": h, "members": [d]})

    regions = []
    for r in rows:
        ms = sorted(r["members"], key=lambda d: d["box"][0])
        boxes = np.array([m["box"] for m in ms])
        regions.append({
            "box": [boxes[:, 0].min(), boxes[:, 1].min(), boxes[:, 2].max(), boxes[:, 3].max()],
            "rapid": " ".join(m["rapid"] for m in ms),
        })
    return regions


def crop(img: np.ndarray, box, pad: int = 6, min_h: int = 64) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    c = img[max(int(y1) - pad, 0): min(int(y2) + pad, h), max(int(x1) - pad, 0): min(int(x2) + pad, w)]
    if c.shape[0] < min_h:   # tiny crops are hard for the vision encoder: upscale
        s = min_h / c.shape[0]
        c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    return c


def glm_read(c: np.ndarray) -> str:
    from ollama import chat   # imported lazily: not needed when RECOGNISER=rapid
    ok, buf = cv2.imencode(".png", c)
    r = chat(
        model=GLM_MODEL,
        messages=[{"role": "user", "content": "Text Recognition:", "images": [buf.tobytes()]}],
        keep_alive="30m",
        options={"temperature": 0, "num_predict": 64},   # a single row never needs more; caps loops
    )
    return r.message.content.strip()


def normalize(regions: list[dict], shape) -> list[dict]:
    h, w = shape[:2]
    return [{"text": r["text"], "rapid": r["rapid"],
             "box": [int(r["box"][0] / w * 1000), int(r["box"][1] / h * 1000),
                     int(r["box"][2] / w * 1000), int(r["box"][3] / h * 1000)]}
            for r in regions]


class Recogniser:
    def __init__(self, mode: str = "glm", engine=None, glm: Callable[[np.ndarray], str] = glm_read):
        if mode not in ("glm", "rapid"):
            raise ValueError(f"mode must be 'glm' or 'rapid', got {mode!r}")
        self.mode, self._engine, self._glm = mode, engine, glm

    @property
    def engine(self):
        if self._engine is None:   # loaded once, on first use
            from rapidocr import RapidOCR
            self._engine = RapidOCR()
        return self._engine

    def detect(self, img: np.ndarray) -> list[dict]:
        result = self.engine(img)
        if result is None or result.boxes is None:
            return []
        dets = []
        for box, txt in zip(result.boxes, result.txts):
            x1, y1 = box.min(axis=0)
            x2, y2 = box.max(axis=0)
            dets.append({"box": [float(x1), float(y1), float(x2), float(y2)], "rapid": txt})
        return dets

    def read(self, img: np.ndarray) -> list[dict]:
        try:
            regions = merge_rows(self.detect(img))
        except Exception as e:
            raise OcrError(f"detection failed: {e}") from e
        for r in regions:
            r["text"] = r["rapid"]
            if self.mode == "glm":
                try:
                    r["text"] = self._glm(crop(img, r["box"]))
                except Exception as e:   # Ollama down or a 500: keep this region's RapidOCR text
                    log.warning("glm-ocr failed for a region, using RapidOCR text: %s", str(e)[:80])
        return normalize(regions, img.shape)
