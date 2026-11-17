import hashlib

from PIL import Image

from bot.preprocess import preprocess


def make(path, size, orientation=None, color=(255, 0, 0)):
    im = Image.new("RGB", size, color)
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    im.save(path, exif=exif)


def test_exif_rotated_image_comes_out_upright(tmp_path):
    p = tmp_path / "a.jpg"
    make(p, (200, 100), orientation=6)      # stored landscape, should display portrait
    out = preprocess(p)
    assert out.shape[:2] == (200, 100)


def test_large_image_is_downscaled_keeping_aspect(tmp_path):
    p = tmp_path / "b.jpg"
    make(p, (3200, 1600))
    h, w = preprocess(p).shape[:2]
    assert (w, h) == (1600, 800)


def test_small_image_is_not_upscaled(tmp_path):
    p = tmp_path / "c.jpg"
    make(p, (300, 400))
    assert preprocess(p).shape[:2] == (400, 300)


def test_returns_bgr(tmp_path):
    p = tmp_path / "d.png"
    make(p, (10, 10), color=(255, 0, 0))     # pure red in RGB
    b, g, r = preprocess(p)[0, 0]
    assert (int(b), int(g), int(r)) == (0, 0, 255)


def test_input_file_is_unchanged(tmp_path):
    p = tmp_path / "e.jpg"
    make(p, (3000, 2000), orientation=3)
    before = hashlib.sha256(p.read_bytes()).hexdigest()
    preprocess(p)
    assert hashlib.sha256(p.read_bytes()).hexdigest() == before
