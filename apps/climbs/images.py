import uuid
import warnings
from contextlib import suppress
from io import BytesIO
from math import sqrt
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_ROUTE_IMAGE_BYTES = 8 * 1024 * 1024
MAX_ROUTE_IMAGE_PIXELS = 36_000_000
MAX_ROUTE_IMAGE_SIDE = 12_000
MAX_ROUTE_IMAGE_COUNT = 4
MAX_MERGED_IMAGE_WIDTH = 1_600
ALLOWED_ROUTE_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_ROUTE_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_ROUTE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
FORMAT_FOR_SUFFIX = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
FORMAT_FOR_CONTENT_TYPE = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def route_image_upload_path(instance: Any, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"routes/{instance.climbing_route_id}/{uuid.uuid4().hex}{suffix}"


def validate_route_image(upload: Any) -> None:
    suffix = Path(str(upload.name)).suffix.lower()
    if suffix not in ALLOWED_ROUTE_IMAGE_SUFFIXES:
        raise ValidationError(_("Upload a JPEG, PNG or WebP image."))
    if upload.size > MAX_ROUTE_IMAGE_BYTES:
        raise ValidationError(_("The image must not exceed 8 MB."))

    content_type = getattr(upload, "content_type", None)
    if content_type and content_type not in ALLOWED_ROUTE_IMAGE_CONTENT_TYPES:
        raise ValidationError(_("The uploaded file has an invalid content type."))

    try:
        upload.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as image:
                image_format = image.format
                width, height = image.size
                frames = getattr(image, "n_frames", 1)
                image.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Warning) as error:
        raise ValidationError(_("The uploaded file is not a valid safe image.")) from error
    finally:
        with suppress(AttributeError, OSError):
            upload.seek(0)

    if image_format not in ALLOWED_ROUTE_IMAGE_FORMATS:
        raise ValidationError(_("Upload a JPEG, PNG or WebP image."))
    if image_format != FORMAT_FOR_SUFFIX[suffix]:
        raise ValidationError(_("The image content does not match its file extension."))
    if content_type and image_format != FORMAT_FOR_CONTENT_TYPE[content_type]:
        raise ValidationError(_("The image content does not match its content type."))
    if width > MAX_ROUTE_IMAGE_SIDE or height > MAX_ROUTE_IMAGE_SIDE:
        raise ValidationError(_("The image dimensions are too large."))
    if width * height > MAX_ROUTE_IMAGE_PIXELS:
        raise ValidationError(_("The image contains too many pixels."))
    if frames != 1:
        raise ValidationError(_("Animated images are not supported."))


def merge_route_images_vertically(uploads: list[Any]) -> ContentFile:
    """Return one safe JPEG containing the supplied images from top to bottom."""
    if not uploads:
        raise ValidationError(_("Select at least one image."))
    if len(uploads) > MAX_ROUTE_IMAGE_COUNT:
        raise ValidationError(
            _("You can upload at most %(limit)s images at once."),
            params={"limit": MAX_ROUTE_IMAGE_COUNT},
        )

    prepared_images: list[Image.Image] = []
    try:
        for upload in uploads:
            validate_route_image(upload)
            prepared_images.append(_open_route_image(upload))

        target_width = min(
            MAX_MERGED_IMAGE_WIDTH,
            *(image.width for image in prepared_images),
        )
        resized_images = _resize_for_vertical_merge(prepared_images, target_width)
        total_height = sum(image.height for image in resized_images)
        scale = min(
            1.0,
            MAX_ROUTE_IMAGE_SIDE / total_height,
            sqrt(MAX_ROUTE_IMAGE_PIXELS / (target_width * total_height)),
        )
        if scale < 1.0:
            for image in resized_images:
                image.close()
            target_width = max(1, int(target_width * scale))
            resized_images = _resize_for_vertical_merge(prepared_images, target_width)
            total_height = sum(image.height for image in resized_images)

        merged = Image.new("RGB", (target_width, total_height), color="white")
        offset_y = 0
        for image in resized_images:
            merged.paste(image, (0, offset_y))
            offset_y += image.height
            image.close()

        try:
            return _encode_merged_image(merged)
        finally:
            merged.close()
    finally:
        for image in prepared_images:
            image.close()
        for upload in uploads:
            with suppress(AttributeError, OSError):
                upload.seek(0)


def _open_route_image(upload: Any) -> Image.Image:
    upload.seek(0)
    with Image.open(upload) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            rgba_image = image.convert("RGBA")
            rgb_image = Image.new("RGB", rgba_image.size, color="white")
            rgb_image.paste(rgba_image, mask=rgba_image.getchannel("A"))
            rgba_image.close()
            return rgb_image
        return image.convert("RGB")


def _resize_for_vertical_merge(
    images: list[Image.Image],
    target_width: int,
) -> list[Image.Image]:
    resized_images = []
    for image in images:
        target_height = max(1, round(image.height * target_width / image.width))
        resized_images.append(
            image.resize(
                (target_width, target_height),
                Image.Resampling.LANCZOS,
            )
        )
    return resized_images


def _encode_merged_image(image: Image.Image) -> ContentFile:
    working_image = image
    owns_working_image = False
    try:
        for _resize_attempt in range(5):
            for quality in (88, 80, 72, 64):
                buffer = BytesIO()
                working_image.save(
                    buffer,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                    progressive=True,
                )
                if buffer.tell() <= MAX_ROUTE_IMAGE_BYTES:
                    upload = ContentFile(
                        buffer.getvalue(),
                        name="combined-route-image.jpg",
                    )
                    upload.content_type = "image/jpeg"  # type: ignore[attr-defined]
                    validate_route_image(upload)
                    return upload

            new_size = (
                max(1, round(working_image.width * 0.85)),
                max(1, round(working_image.height * 0.85)),
            )
            smaller_image = working_image.resize(new_size, Image.Resampling.LANCZOS)
            if owns_working_image:
                working_image.close()
            working_image = smaller_image
            owns_working_image = True
    finally:
        if owns_working_image:
            working_image.close()

    raise ValidationError(
        _("The combined image is too large. Choose fewer or smaller images."),
    )
