from types import SimpleNamespace
from typing import Any

import pytest
from django.core.files.base import ContentFile

from apps.core import storage as storage_module


class FakeUploader:
    def __init__(self) -> None:
        self.upload_calls: list[tuple[Any, dict[str, Any]]] = []
        self.destroy_calls: list[tuple[str, dict[str, Any]]] = []

    def upload(self, content: Any, **options: Any) -> dict[str, str]:
        self.upload_calls.append((content, options))
        return {"public_id": "routes/7/generated", "format": "webp"}

    def destroy(self, public_id: str, **options: Any) -> None:
        self.destroy_calls.append((public_id, options))


def test_cloudinary_storage_upload_url_and_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    config_calls: list[dict[str, Any]] = []
    cloudinary = SimpleNamespace(config=lambda **options: config_calls.append(options))
    uploader = FakeUploader()
    url_calls: list[tuple[str, dict[str, Any]]] = []

    def url_builder(public_id: str, **options: Any) -> tuple[str, dict[str, Any]]:
        url_calls.append((public_id, options))
        return "https://media.example/routes/7/generated.webp", {}

    monkeypatch.setattr(
        storage_module,
        "_cloudinary_components",
        lambda: (cloudinary, uploader, url_builder),
    )
    storage = storage_module.CloudinaryMediaStorage()
    content = ContentFile(b"image-content")

    stored_name = storage._save("routes/7/random.png", content)
    delivery_url = storage.url(stored_name)
    storage.delete(stored_name)

    assert config_calls == [{"secure": True}]
    assert stored_name == "routes/7/generated.webp"
    assert uploader.upload_calls == [
        (
            content,
            {
                "public_id": "routes/7/random",
                "overwrite": False,
                "resource_type": "image",
            },
        )
    ]
    assert url_calls == [
        (
            "routes/7/generated",
            {"format": "webp", "resource_type": "image", "secure": True},
        )
    ]
    assert delivery_url == "https://media.example/routes/7/generated.webp"
    assert uploader.destroy_calls == [
        (
            "routes/7/generated",
            {"invalidate": True, "resource_type": "image"},
        )
    ]


def test_cloudinary_storage_uses_unique_names_without_network_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloudinary = SimpleNamespace(config=lambda **options: None)
    monkeypatch.setattr(
        storage_module,
        "_cloudinary_components",
        lambda: (cloudinary, FakeUploader(), lambda *args, **kwargs: ("", {})),
    )
    storage = storage_module.CloudinaryMediaStorage()

    assert not storage.exists("routes/random.png")
    storage.delete("")
    with pytest.raises(ValueError):
        storage.url(None)
