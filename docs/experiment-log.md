
## OCR Trial #1

Date: November 10, 2026

I will try to run ocr inferences on 20 pictures from my test data and see how initial performance compares across rapid-ocr, tesseract, paddle-ocr, and a vision language model running on my Lenovo Y530

Goals
- identify performance gaps in untrained ocr models for my images
- obtain differences in accuracy and inference times across ocr models

Results



## MVP parsing evaluation: RapidOCR text vs the exp3 hybrid

Date: November 17, 2026

Both recognisers were run over all 316 images in `images/train` (after the MVP preprocessing: EXIF rotation, 1600 px max) and the same parsers were scored against `labels/train.csv`. Commands: `python eval/dump_items.py rapid|glm`, then `python eval/score.py eval/cache/<mode>`.

Per-field accuracy, all 316 images:

| Recogniser | provider | amount | date | time | reference | status | median s/image | p95 s/image |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rapid` (RapidOCR text) | 99% | 98% | 96% | 94% | 93% | 99% | 0.81 | 1.15 |
| `glm` (RapidOCR boxes + glm-ocr per row) | 99% | 97% | 97% | 97% | 93% | 99% | 5.86 | 11.38 |

By Provider, `glm` / `rapid` (reference accuracy): GCash 99 / 98, GoTyme 89 / 91, MariBank 94 / 92, BPI 97 / 97, BDO 94 / 94, Maya 64 / 82, other 71 / 71.

Findings
- glm-ocr gains on date and time (+1 and +3 points) and loses 1 point on amount. Reference and status are unchanged. That is a small effect for about 7 times the latency.
- The parsers were written and tuned against the RapidOCR text, which favours `rapid`. glm-ocr output has different spacing and may need its own rules before the comparison is fair.
- GoTyme references: glm-ocr is worse here (89% vs 91%).
- Maya amount stays at 64% in both: the labels disagree on whether a Maya amount includes the fee, so the parser is generic. Maya is 11 images.
- `other` dates and references stay near 75%: these receipts are too varied for one parser.
- Weak spots in both: dates that RapidOCR drops (about 10 images), and `PM` read as `FM` or cut off.
- The MVP default is still `RECOGNISER=glm` as decided. The numbers do not show it is worth the latency yet. Setting `RECOGNISER=rapid` needs no code change.
