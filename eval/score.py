"""Score the parser against labels/train.csv using cached recogniser output.

    python eval/score.py [cache_dir] [--show FIELD [PROVIDER]]
"""
import csv
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocr.parse import parse

args = [a for a in sys.argv[1:]]
show = None
if "--show" in args:
    i = args.index("--show")
    show = args[i + 1:i + 3]
    args = args[:i]
cache = Path(args[0] if args else "eval/cache/rapid")


def dec(s):
    try:
        return Decimal(s) if s not in ("", None) else None
    except InvalidOperation:
        return None


def ref(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper() or None


FIELDS = {
    "provider": lambda p, l: p.provider == (l["provider"] or "other"),
    "amount": lambda p, l: p.amount == dec(l["amount.value"]) if dec(l["amount.value"]) is not None else p.amount is None,
    "date": lambda p, l: p.printed_date == (l["date.value"] or None),
    "time": lambda p, l: p.printed_time == (l["date.time"] or None),
    "reference": lambda p, l: p.reference_number == ref(l["reference_number.value"]),
    "status": lambda p, l: p.txn_status == (l["status"] or "successful"),
}

labels = {Path(r["image_file"]).stem: r for r in csv.DictReader(open("labels/train.csv"))}
hits = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for f in sorted(cache.glob("*.json")):
    row = labels.get(f.stem)
    if row is None:
        continue
    items = json.loads(f.read_text())["items"]
    p = parse(items)
    for name, ok in FIELDS.items():
        good = ok(p, row)
        for prov in (row["provider"] or "other", "ALL"):
            hits[prov][name][0] += good
            hits[prov][name][1] += 1
        if show and show[0] == name and not good and (len(show) < 2 or show[1] == row["provider"]):
            want = {"amount": row["amount.value"], "date": row["date.value"], "time": row["date.time"],
                    "reference": row["reference_number.value"], "status": row["status"], "provider": row["provider"]}[name]
            got = {"amount": p.amount, "date": p.printed_date, "time": p.printed_time,
                   "reference": p.reference_number, "status": p.txn_status, "provider": p.provider}[name]
            print(f"MISS {f.stem} {name}: want={want!r} got={got!r}")

print(f"{'provider':10}" + "".join(f"{n:>11}" for n in FIELDS) + "      n")
for prov in sorted(hits, key=lambda k: (k == "ALL", k)):
    n = next(iter(hits[prov].values()))[1]
    print(f"{prov:10}" + "".join(f"{hits[prov][k][0] / hits[prov][k][1]:>10.0%} " for k in FIELDS) + f"{n:>7}")
