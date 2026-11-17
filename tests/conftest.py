import pytest


def make_items(*texts):
    """Items shaped like the recogniser's output, one per row, top to bottom."""
    return [{"text": t, "rapid": t, "box": [0, i * 40, 900, i * 40 + 30]} for i, t in enumerate(texts)]


@pytest.fixture
def items():
    return make_items
