"""Pull the image reference out of a Telegram message (photo or image document)."""


def extract_image(msg: dict) -> dict | None:
    if msg.get("photo"):
        p = msg["photo"][-1]   # largest size = least compression
        return dict(source="photo", file_id=p["file_id"], file_unique_id=p["file_unique_id"],
                    original_name=None, mime_type="image/jpeg", file_size=p.get("file_size"),
                    width=p.get("width"), height=p.get("height"))
    doc = msg.get("document")
    if doc and (doc.get("mime_type") or "").startswith("image/"):
        return dict(source="document", file_id=doc["file_id"], file_unique_id=doc["file_unique_id"],
                    original_name=doc.get("file_name"), mime_type=doc["mime_type"],
                    file_size=doc.get("file_size"), width=None, height=None)
    return None


_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic"}


def extension(img: dict) -> str:
    return _EXT.get(img.get("mime_type") or "", ".jpg")
