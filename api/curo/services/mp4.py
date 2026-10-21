"""Read an upload's length and size from its MP4/MOV container (ISO base media boxes).

Only the headers are read: `moov/mvhd` (timescale and duration) and each track's `tkhd`
(width and height in 16.16 fixed point). Nothing is decoded, so this is fast and safe on any
file a creator picks; a file that isn't MP4 or MOV is refused with a plain reason.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"udta"}
MAX_SECONDS = 90.0


class NotAVideo(ValueError):
    """A file the Simulator can't take, with the reason in plain words."""


@dataclass(frozen=True)
class VideoMeta:
    duration_s: float
    width: int | None
    height: int | None
    brand: str


def _boxes(data: bytes, start: int, end: int):
    """(type, payload start, box end) for each box between start and end."""
    i = start
    while i + 8 <= end:
        size, kind = struct.unpack(">I4s", data[i : i + 8])
        header = 8
        if size == 1:  # 64-bit size follows
            if i + 16 > end:
                return
            size = struct.unpack(">Q", data[i + 8 : i + 16])[0]
            header = 16
        elif size == 0:  # to the end of the file
            size = end - i
        if size < header or i + size > end:
            return
        yield kind, i + header, i + size
        i += size


def read(data: bytes) -> VideoMeta:
    if len(data) < 16 or data[4:8] != b"ftyp":
        raise NotAVideo("That file isn't an MP4 or MOV video.")
    brand = data[8:12].decode("latin-1").strip()
    duration = None
    width = height = None

    def walk(start: int, end: int) -> None:
        nonlocal duration, width, height
        for kind, body, stop in _boxes(data, start, end):
            if kind == b"mvhd":
                version = data[body]
                if version == 1:
                    timescale, length = struct.unpack(">IQ", data[body + 20 : body + 32])
                else:
                    timescale, length = struct.unpack(">II", data[body + 12 : body + 20])
                if timescale:
                    duration = length / timescale
            elif kind == b"tkhd":
                version = data[body]
                # version 0: 24 bytes of times/ids, 16 reserved/layer/volume, 36 matrix → 76
                offset = body + (88 if version == 1 else 76)
                if offset + 8 <= stop:
                    w, h = struct.unpack(">II", data[offset : offset + 8])
                    if w and h and width is None:
                        width, height = w >> 16, h >> 16
            elif kind in CONTAINERS:
                walk(body, stop)

    walk(0, len(data))
    if duration is None:
        raise NotAVideo("Curo couldn't read this video's length. Try exporting it again as MP4.")
    return VideoMeta(round(duration, 2), width, height, brand)


def check(data: bytes) -> VideoMeta:
    """What the Simulator accepts: an MP4 or MOV of at most 90 seconds (the Reels limit)."""
    meta = read(data)
    if meta.duration_s > MAX_SECONDS:
        raise NotAVideo(
            f"This video is {round(meta.duration_s)} seconds long. The Simulator takes reels of "
            f"up to {round(MAX_SECONDS)} seconds."
        )
    if meta.duration_s <= 0:
        raise NotAVideo("This video has no length. Try exporting it again as MP4.")
    return meta


def build(duration_s: float, width: int, height: int, extra: bytes = b"") -> bytes:
    """A minimal, valid container (ftyp, an optional free box, moov/mvhd/trak/tkhd): enough for
    `read` and for tests and the demo's sample recordings. It carries no picture."""

    def box(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I4s", 8 + len(payload), kind) + payload

    timescale = 1000
    mvhd = struct.pack(">B3xIIII", 0, 0, 0, timescale, round(duration_s * timescale))
    mvhd += struct.pack(">IH10x", 0x00010000, 0x0100) + bytes(36) + bytes(24) + struct.pack(">I", 2)
    tkhd = struct.pack(">B3xIIIII", 0, 0, 0, 1, 0, round(duration_s * timescale))
    tkhd += bytes(8) + struct.pack(">hhH2x", 0, 0, 0) + bytes(36)
    tkhd += struct.pack(">II", width << 16, height << 16)
    parts = [box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2mp41")]
    if extra:
        parts.append(box(b"free", extra))
    parts.append(box(b"moov", box(b"mvhd", mvhd) + box(b"trak", box(b"tkhd", tkhd))))
    return b"".join(parts)
