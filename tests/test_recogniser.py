from types import SimpleNamespace

import numpy as np
import pytest

from ocr.recognise import OcrError, Recogniser, crop, merge_rows

IMG = np.zeros((200, 400, 3), dtype=np.uint8)


def box(x1, y1, x2, y2):
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=float)


class FakeEngine:
    def __init__(self, boxes, txts):
        self.result = SimpleNamespace(boxes=boxes, txts=txts)
        self.calls = 0

    def __call__(self, img):
        self.calls += 1
        return self.result


def engine():
    return FakeEngine([box(10, 10, 60, 30), box(200, 12, 280, 32), box(10, 100, 90, 120)],
                      ["Amount", "300.00", "Ref No."])


def test_boxes_on_one_row_merge_left_to_right():
    regions = merge_rows([{"box": [200, 12, 280, 32], "rapid": "300.00"}, {"box": [10, 10, 60, 30], "rapid": "Amount"}])
    assert [r["rapid"] for r in regions] == ["Amount 300.00"]


def test_item_shape_and_box_scale():
    items = Recogniser("rapid", engine=engine()).read(IMG)
    assert [i["text"] for i in items] == ["Amount 300.00", "Ref No."]
    assert items[0]["box"] == [25, 50, 700, 160]   # 0-1000 of a 400x200 image
    assert set(items[0]) == {"text", "rapid", "box"}


def test_glm_text_replaces_rapid_text():
    items = Recogniser("glm", engine=engine(), glm=lambda c: "GLM").read(IMG)
    assert [i["text"] for i in items] == ["GLM", "GLM"] and items[0]["rapid"] == "Amount 300.00"


def test_glm_error_falls_back_per_region_and_does_not_abort():
    def flaky(c, n=[0]):
        n[0] += 1
        if n[0] == 1:
            raise RuntimeError("500")
        return "GLM"
    items = Recogniser("glm", engine=engine(), glm=flaky).read(IMG)
    assert [i["text"] for i in items] == ["Amount 300.00", "GLM"]


def test_rapid_mode_never_calls_glm():
    def boom(c):
        raise AssertionError("glm called")
    Recogniser("rapid", engine=engine(), glm=boom).read(IMG)


def test_detection_failure_raises_ocr_error():
    class Broken:
        def __call__(self, img):
            raise RuntimeError("onnx")
    with pytest.raises(OcrError):
        Recogniser("rapid", engine=Broken()).read(IMG)


def test_nothing_detected_gives_no_items():
    assert Recogniser("rapid", engine=FakeEngine(None, None)).read(IMG) == []


def test_engine_is_reused_across_images():
    e = engine()
    r = Recogniser("rapid", engine=e)
    r.read(IMG); r.read(IMG)
    assert r._engine is e and e.calls == 2


def test_small_crops_are_upscaled():
    assert crop(IMG, [10, 10, 60, 20]).shape[0] >= 64


def test_bad_mode():
    with pytest.raises(ValueError):
        Recogniser("gpt")
