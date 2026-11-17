"""Recognise every image in a folder and cache the item lists as JSON (resumable).

    python eval/dump_items.py rapid|glm [images_dir] [out_dir]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.preprocess import preprocess
from ocr.recognise import OcrError, Recogniser

mode = sys.argv[1]
src = Path(sys.argv[2] if len(sys.argv) > 2 else "images/train")
out = Path(sys.argv[3] if len(sys.argv) > 3 else f"eval/cache/{mode}")
out.mkdir(parents=True, exist_ok=True)
rec = Recogniser(mode)
for p in sorted(src.iterdir()):
    dest = out / f"{p.stem}.json"
    if dest.exists() or not p.is_file():
        continue
    t = time.perf_counter()
    try:
        items, err = rec.read(preprocess(p)), None
    except (OcrError, OSError) as e:
        items, err = [], str(e)
    dest.write_text(json.dumps({"image": p.name, "seconds": round(time.perf_counter() - t, 2),
                                "error": err, "items": items}, ensure_ascii=False))
    print(p.name, len(items), flush=True)
