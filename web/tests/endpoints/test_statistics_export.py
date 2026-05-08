from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import io
import struct
import zipfile

from web.services import now_utc
from web.tests.fixtures import run_async


def _login_admin(client, state):
    state.settings = replace(state.settings, admin_emails=frozenset({"admin@example.com"}))
    run_async(
        state.users_collection.insert_one(
            {
                "email": "admin@example.com",
                "is_admin": True,
            }
        )
    )
    user = state.users_collection.docs[0]
    run_async(
        state.sessions_collection.insert_one(
            {
                "token": "admin-token",
                "user_id": user["_id"],
                "created_at": now_utc(),
                "expires_at": now_utc() + timedelta(hours=1),
            }
        )
    )
    client.cookies.set(state.settings.session_cookie_name, "admin-token")


def test_statistics_zip_export_streams_windows_compatible_headers(client, state):
    _login_admin(client, state)
    run_async(
        state.registrations_collection.insert_one(
            {
                "created_at": now_utc(),
                "last_name": "Тест:",
                "first_name": "Админ",
                "publication_file": {
                    "filename": "bad:name?.docx",
                    "data": b"publication",
                },
                "review_file": {
                    "filename": "bad:name?.docx",
                    "data": b"review",
                },
            }
        )
    )

    response = client.get("/admin/statistics/export.zip")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    archive_data = response.content
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == [
            "Тест_ Админ/bad_name_.docx",
            "Тест_ Админ/bad_name_(1).docx",
        ]
        for info in archive.infolist():
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.flag_bits & 0x08 == 0

            local_header = archive_data[info.header_offset : info.header_offset + 30]
            (
                signature,
                _version,
                flag_bits,
                compress_type,
                _mtime,
                _mdate,
                crc,
                compressed_size,
                file_size,
                _name_len,
                _extra_len,
            ) = struct.unpack("<IHHHHHIIIHH", local_header)
            assert signature == 0x04034B50
            assert flag_bits & 0x08 == 0
            assert compress_type == zipfile.ZIP_STORED
            assert crc == info.CRC
            assert compressed_size == info.compress_size
            assert file_size == info.file_size
