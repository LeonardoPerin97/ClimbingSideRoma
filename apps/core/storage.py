from pathlib import PurePosixPath
from typing import Any

from django.core.files.storage import Storage


def _cloudinary_components() -> tuple[Any, Any, Any]:
    import cloudinary
    import cloudinary.uploader
    from cloudinary.utils import cloudinary_url

    return cloudinary, cloudinary.uploader, cloudinary_url


class CloudinaryMediaStorage(Storage):
    """Small Django storage adapter backed by the official Cloudinary SDK."""

    def __init__(self) -> None:
        self.cloudinary, self.uploader, self.url_builder = _cloudinary_components()
        self.cloudinary.config(secure=True)

    def _save(self, name: str, content: Any) -> str:
        public_id = PurePosixPath(name).with_suffix("").as_posix()
        result = self.uploader.upload(
            content,
            public_id=public_id,
            overwrite=False,
            resource_type="image",
        )
        stored_public_id = str(result["public_id"])
        stored_format = str(result["format"])
        return f"{stored_public_id}.{stored_format}"

    def delete(self, name: str) -> None:
        if not name:
            return
        public_id = PurePosixPath(name).with_suffix("").as_posix()
        self.uploader.destroy(
            public_id,
            invalidate=True,
            resource_type="image",
        )

    def exists(self, name: str) -> bool:
        del name
        # Media names contain a UUID, so a network existence check is unnecessary.
        return False

    def url(self, name: str | None) -> str:
        if not name:
            raise ValueError("A stored image name is required.")
        path = PurePosixPath(name)
        public_id = path.with_suffix("").as_posix()
        image_format = path.suffix.lstrip(".") or None
        url, _ = self.url_builder(
            public_id,
            format=image_format,
            resource_type="image",
            secure=True,
        )
        return str(url)
