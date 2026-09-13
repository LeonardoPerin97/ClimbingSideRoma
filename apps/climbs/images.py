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
EXIF_ORIENTATION_TAG = 274
EXIF_ORIENTATIONS_THAT_SWAP_AXES = {5, 6, 7, 8}
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

    try:
        for upload in uploads:
            validate_route_image(upload)

        source_sizes = [_oriented_image_size(upload) for upload in uploads]
        target_width, target_heights = _merged_image_dimensions(source_sizes)
        total_height = sum(target_heights)

        merged = Image.new("RGB", (target_width, total_height), color="white")
        try:
            offset_y = 0
            for upload, target_height in zip(uploads, target_heights, strict=True):
                image = _prepare_image_for_merge(
                    upload,
                    (target_width, target_height),
                )
                try:
                    merged.paste(image, (0, offset_y))
                    offset_y += target_height
                finally:
                    image.close()
            return _encode_merged_image(merged)
        finally:
            merged.close()
    finally:
        for upload in uploads:
            with suppress(AttributeError, OSError):
                upload.seek(0)


def _oriented_image_size(upload: Any) -> tuple[int, int]:
    upload.seek(0)
    try:
        with Image.open(upload) as image:
            width, height = image.size
            orientation = image.getexif().get(EXIF_ORIENTATION_TAG, 1)
            if orientation in EXIF_ORIENTATIONS_THAT_SWAP_AXES:
                return height, width
            return width, height
    finally:
        with suppress(AttributeError, OSError):
            upload.seek(0)


def _merged_image_dimensions(
    source_sizes: list[tuple[int, int]],
) -> tuple[int, list[int]]:
    target_width = min(MAX_MERGED_IMAGE_WIDTH, *(width for width, _height in source_sizes))

    def target_heights(width: int) -> list[int]:
        return [
            max(1, round(source_height * width / source_width))
            for source_width, source_height in source_sizes
        ]

    heights = target_heights(target_width)
    total_height = sum(heights)
    scale = min(
        1.0,
        MAX_ROUTE_IMAGE_SIDE / total_height,
        sqrt(MAX_ROUTE_IMAGE_PIXELS / (target_width * total_height)),
    )
    target_width = max(1, int(target_width * scale))
    heights = target_heights(target_width)

    while (
        sum(heights) > MAX_ROUTE_IMAGE_SIDE or target_width * sum(heights) > MAX_ROUTE_IMAGE_PIXELS
    ):
        if target_width <= 1:
            raise ValidationError(
                _("The combined image is too large. Choose fewer or smaller images."),
            )
        target_width -= 1
        heights = target_heights(target_width)

    return target_width, heights


def _prepare_image_for_merge(
    upload: Any,
    target_size: tuple[int, int],
) -> Image.Image:
    upload.seek(0)
    try:
        with Image.open(upload) as source:
            orientation = source.getexif().get(EXIF_ORIENTATION_TAG, 1)
            draft_size = (
                (target_size[1], target_size[0])
                if orientation in EXIF_ORIENTATIONS_THAT_SWAP_AXES
                else target_size
            )
            if source.format == "JPEG":
                source.draft("RGB", draft_size)

            ImageOps.exif_transpose(source, in_place=True)
            source.thumbnail(
                target_size,
                Image.Resampling.LANCZOS,
                reducing_gap=3.0,
            )

            if source.mode in {"RGBA", "LA"} or (
                source.mode == "P" and "transparency" in source.info
            ):
                rgba_image = source.convert("RGBA")
                rgb_image = Image.new("RGB", rgba_image.size, color="white")
                rgb_image.paste(rgba_image, mask=rgba_image.getchannel("A"))
                rgba_image.close()
            else:
                rgb_image = source.convert("RGB")

            if rgb_image.size == target_size:
                return rgb_image
            resized_image = rgb_image.resize(
                target_size,
                Image.Resampling.LANCZOS,
            )
            rgb_image.close()
            return resized_image
    finally:
        with suppress(AttributeError, OSError):
            upload.seek(0)


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
