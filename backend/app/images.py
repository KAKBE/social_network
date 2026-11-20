"""Checks an uploaded photo before it is stored. The original filename is never used."""

import struct

MAX_BYTES = 5 * 1024 * 1024
MAX_EDGE = 4096


class ImageRejected(Exception):
    pass


def inspect_image(data: bytes) -> str:
    """Return the stored extension: png, jpg or webp."""
    if len(data) > MAX_BYTES:
        raise ImageRejected("Файл больше 5 МБ")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = _png_size(data)
        extension = "png"
    elif data.startswith(b"\xff\xd8\xff"):
        width, height = _jpeg_size(data)
        extension = "jpg"
    elif len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        width, height = _webp_size(data)
        extension = "webp"
    else:
        raise ImageRejected("Нужна фотография JPEG, PNG или WebP")
    if width < 1 or height < 1 or width > MAX_EDGE or height > MAX_EDGE:
        raise ImageRejected("Сторона фотографии не больше 4096 пикселей")
    return extension


def _png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ImageRejected("Повреждённый PNG")
    return struct.unpack(">II", data[16:24])


def _jpeg_size(data: bytes) -> tuple[int, int]:
    index = 2
    while index + 8 < len(data):
        if data[index] != 0xFF:
            raise ImageRejected("Повреждённый JPEG")
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        length = struct.unpack(">H", data[index : index + 2])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            try:
                height, width = struct.unpack(">HH", data[index + 3 : index + 7])
            except struct.error:
                raise ImageRejected("Повреждённый JPEG") from None
            return width, height
        index += length
    raise ImageRejected("Не удалось прочитать размер JPEG")


def _webp_size(data: bytes) -> tuple[int, int]:
    if len(data) < 30:
        raise ImageRejected("Повреждённый WebP")
    kind = data[12:16]
    if kind == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    if kind == b"VP8 ":
        start = data.find(b"\x9d\x01\x2a")
        if start < 0 or start + 7 > len(data):
            raise ImageRejected("Повреждённый WebP")
        width, height = struct.unpack("<HH", data[start + 3 : start + 7])
        return width & 0x3FFF, height & 0x3FFF
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ImageRejected("Повреждённый WebP")
