import base64
from io import BytesIO

from PIL import Image

import storage


def _png_data_url() -> str:
    image = Image.new("RGB", (3, 3), color=(20, 80, 120))
    output = BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def test_local_photo_storage_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "USE_SUPABASE", False)
    monkeypatch.setattr(storage, "STORE_DIR", tmp_path)

    image_ref = storage.save_selfie(_png_data_url())
    assert image_ref.endswith(".png")
    photo, media_type = storage.read_selfie(image_ref)
    assert photo.startswith(b"\x89PNG")
    assert media_type == "image/png"

    storage.delete_selfie(image_ref)
    assert not (tmp_path / image_ref).exists()


def test_supabase_photo_storage_uses_private_object_api(monkeypatch):
    calls = []
    image_bytes = b"supabase-image-bytes"

    def fake_request(method, object_path, raw=None, content_type=None):
        calls.append((method, object_path, raw, content_type))
        return image_bytes if method == "GET" else b""

    monkeypatch.setattr(storage, "USE_SUPABASE", True)
    monkeypatch.setattr(storage, "_supabase_request", fake_request)

    image_ref = storage.save_selfie(_png_data_url())
    assert image_ref.endswith(".png")
    assert calls[0][0] == "POST"
    assert calls[0][1] == image_ref
    assert calls[0][3] == "image/png"

    photo, media_type = storage.read_selfie(image_ref)
    assert photo == image_bytes
    assert media_type == "image/png"
    assert calls[1][0] == "GET"

    storage.delete_selfie(image_ref)
    assert calls[2][0] == "DELETE"
