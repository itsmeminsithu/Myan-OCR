"""Validated image loading and OCR-oriented, non-destructive transformations."""
from __future__ import annotations

from io import BytesIO
import warnings

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

MAX_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_EDGE = 4096
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageInputError(ValueError):
    pass


def load_image(payload: bytes, rotate: int = 0) -> Image.Image:
    if not payload:
        raise ImageInputError('Choose an image first.')
    if len(payload) > MAX_BYTES:
        raise ImageInputError('Image exceeds 12 MB. Choose a smaller image.')
    if rotate not in (0, 90, 180, 270):
        raise ImageInputError('Rotation must be 0, 90, 180 or 270 degrees.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(BytesIO(payload))
            if image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ImageInputError('Only JPEG, PNG and WebP are supported.')
            image.load()
            if image.width * image.height > MAX_PIXELS:
                raise ImageInputError('Image exceeds the 16 megapixel limit.')
            image = ImageOps.exif_transpose(image)
            if image.mode == 'RGBA' or 'transparency' in image.info:
                rgba = image.convert('RGBA')
                white = Image.new('RGBA', rgba.size, 'white')
                white.alpha_composite(rgba)
                image = white.convert('RGB')
            else:
                image = image.convert('RGB')
            if rotate:
                image = image.rotate(-rotate, expand=True)
            if max(image.size) > MAX_EDGE:
                image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            return image
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageInputError('The uploaded file is not a valid image or is too large.') from exc


def variants(image: Image.Image, mode: str) -> list[tuple[str, Image.Image, int]]:
    """PIL images plus Tesseract page segmentation mode; same coordinate frame across variants."""
    if mode not in ('fast', 'balanced', 'accurate'):
        raise ValueError('Unknown OCR mode.')
    if mode == 'fast':
        return [('original', image, 3)]
    rgb = np.asarray(image.convert('RGB'))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)
    enhanced = Image.fromarray(cv2.cvtColor(clahe, cv2.COLOR_GRAY2RGB))
    choices = [('original', image, 3), ('contrast', enhanced, 6)]
    if mode == 'accurate':
        # Adaptive threshold works better for uneven lighting and low-contrast print in some images.
        blurred = cv2.GaussianBlur(clahe, (3, 3), 0)
        threshold = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 31, 12)
        binary = Image.fromarray(cv2.cvtColor(threshold, cv2.COLOR_GRAY2RGB))
        choices += [('adaptive', binary, 6), ('sparse', enhanced, 11)]
    return choices


def image_to_png_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()
