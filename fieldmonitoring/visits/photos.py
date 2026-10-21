"""Photo evidence helpers (BR-11): perceptual hash and EXIF position."""

from decimal import Decimal

from PIL import Image, ImageOps

GPS_IFD = 0x8825
MAX_PHOTO_BYTES = 1_000_000  # the client compresses to under 300 KB; this is a hard cap


def dhash(image: Image.Image, size: int = 8) -> str:
    """64-bit difference hash as 16 hex characters. Robust to recompression and small shifts."""
    gray = ImageOps.exif_transpose(image).convert("L").resize((size + 1, size), Image.LANCZOS)
    pixels = list(gray.get_flattened_data())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = pixels[row * (size + 1) + col]
            right = pixels[row * (size + 1) + col + 1]
            bits = (bits << 1) | (left > right)
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def _to_degrees(value) -> float:
    d, m, s = (float(x) for x in value)
    return d + m / 60 + s / 3600


def exif_position(image: Image.Image) -> tuple[Decimal, Decimal] | None:
    try:
        gps = image.getexif().get_ifd(GPS_IFD)
        lat = _to_degrees(gps[2]) * (-1 if gps.get(1) == "S" else 1)
        lng = _to_degrees(gps[4]) * (-1 if gps.get(3) == "W" else 1)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return Decimal(f"{lat:.6f}"), Decimal(f"{lng:.6f}")
