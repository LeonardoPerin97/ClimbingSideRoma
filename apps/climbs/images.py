import uuid
import warnings
from contextlib import suppress
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

MAX_ROUTE_IMAGE_BYTES = 8 * 1024 * 1024
MAX_ROUTE_IMAGE_PIXELS = 36_000_000
MAX_ROUTE_IMAGE_SIDE = 12_000
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
