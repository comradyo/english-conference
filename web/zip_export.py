from __future__ import annotations

import binascii
import struct
from collections.abc import Iterable, Iterator
from typing import TypeAlias


ZIP64_LIMIT = 0xFFFFFFFF
ZIP_STORED = 0
UTF8_FLAG = 0x0800
DOS_DATE_1980_01_01 = 33
DOS_TIME_00_00_00 = 0
ZipBytes: TypeAlias = bytes | bytearray | memoryview


def _dos_timestamp() -> tuple[int, int]:
    return DOS_TIME_00_00_00, DOS_DATE_1980_01_01


def _zip64_extra(*values: int) -> bytes:
    payload = b"".join(struct.pack("<Q", value) for value in values)
    return struct.pack("<HH", 0x0001, len(payload)) + payload


def _local_header(name_bytes: bytes, crc: int, file_size: int, offset: int) -> tuple[bytes, bytes]:
    zip64 = file_size > ZIP64_LIMIT or offset > ZIP64_LIMIT
    compressed_size = ZIP64_LIMIT if zip64 else file_size
    uncompressed_size = ZIP64_LIMIT if zip64 else file_size
    extra = _zip64_extra(file_size, file_size) if zip64 else b""
    mtime, mdate = _dos_timestamp()
    header = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        45 if zip64 else 20,
        UTF8_FLAG,
        ZIP_STORED,
        mtime,
        mdate,
        crc,
        compressed_size,
        uncompressed_size,
        len(name_bytes),
        len(extra),
    )
    return header, extra


def _central_header(name_bytes: bytes, crc: int, file_size: int, offset: int) -> bytes:
    size_zip64 = file_size > ZIP64_LIMIT
    offset_zip64 = offset > ZIP64_LIMIT
    zip64_values: list[int] = []
    if size_zip64:
        zip64_values.extend([file_size, file_size])
    if offset_zip64:
        zip64_values.append(offset)
    extra = _zip64_extra(*zip64_values) if zip64_values else b""
    mtime, mdate = _dos_timestamp()
    header = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50,
        45 if (size_zip64 or offset_zip64) else 20,
        45 if (size_zip64 or offset_zip64) else 20,
        UTF8_FLAG,
        ZIP_STORED,
        mtime,
        mdate,
        crc,
        ZIP64_LIMIT if size_zip64 else file_size,
        ZIP64_LIMIT if size_zip64 else file_size,
        len(name_bytes),
        len(extra),
        0,
        0,
        0,
        0,
        ZIP64_LIMIT if offset_zip64 else offset,
    )
    return header + name_bytes + extra


def _end_of_central_directory(file_count: int, central_directory_size: int, central_directory_offset: int, offset: int) -> bytes:
    needs_zip64 = (
        file_count > 0xFFFF
        or central_directory_size > ZIP64_LIMIT
        or central_directory_offset > ZIP64_LIMIT
    )
    if not needs_zip64:
        return struct.pack(
            "<IHHHHIIH",
            0x06054B50,
            0,
            0,
            file_count,
            file_count,
            central_directory_size,
            central_directory_offset,
            0,
        )
    zip64_eocd = struct.pack(
        "<IQHHIIQQQQ",
        0x06064B50,
        44,
        45,
        45,
        0,
        0,
        file_count,
        file_count,
        central_directory_size,
        central_directory_offset,
    )
    zip64_locator = struct.pack("<IIQI", 0x07064B50, 0, offset, 1)
    eocd = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        min(file_count, 0xFFFF),
        min(file_count, 0xFFFF),
        min(central_directory_size, ZIP64_LIMIT),
        min(central_directory_offset, ZIP64_LIMIT),
        0,
    )
    return zip64_eocd + zip64_locator + eocd


class StoredZipStream:
    """Incrementally write a Windows-compatible ZIP without buffering file bodies."""

    def __init__(self) -> None:
        self._central_directory: list[bytes] = []
        self._offset = 0
        self._finalized = False

    def add_file(self, arc_name: str, file_data: ZipBytes) -> Iterator[bytes]:
        if self._finalized:
            raise ValueError("cannot add files after ZIP stream is finalized")
        name_bytes = arc_name.encode("utf-8")
        file_size = len(file_data)
        crc = binascii.crc32(file_data) & 0xFFFFFFFF
        header, extra = _local_header(name_bytes, crc, file_size, self._offset)
        yield header
        yield name_bytes
        if extra:
            yield extra
        yield file_data
        self._central_directory.append(_central_header(name_bytes, crc, file_size, self._offset))
        self._offset += len(header) + len(name_bytes) + len(extra) + file_size

    def finalize(self) -> Iterator[bytes]:
        self._finalized = True
        central_directory_offset = self._offset
        for entry in self._central_directory:
            yield entry
            self._offset += len(entry)
        central_directory_size = self._offset - central_directory_offset
        yield _end_of_central_directory(
            len(self._central_directory),
            central_directory_size,
            central_directory_offset,
            self._offset,
        )


def iter_stored_zip(files: Iterable[tuple[str, ZipBytes]]) -> Iterator[bytes]:
    stream = StoredZipStream()
    for arc_name, file_data in files:
        yield from stream.add_file(arc_name, file_data)
    yield from stream.finalize()
