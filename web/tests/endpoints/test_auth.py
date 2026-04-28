from __future__ import annotations

from fixtures import run_async
from web.security import hash_password


def test_register_account_success(client, state):
    response = client.post(
        "/register-account",
        data={
            "email": "user@example.com",
            "password": "Secret1234",
            "password_repeat": "Secret1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers.get("location") == "/my-registrations"
    assert any("test_session=" in value for value in response.headers.get_list("set-cookie"))

    assert len(state.users_collection.docs) == 1
    assert len(state.sessions_collection.docs) == 1
    assert state.users_collection.docs[0]["email"] == "user@example.com"


def test_register_account_duplicate_email(client, state):
    run_async(
        state.users_collection.insert_one(
            {
                "email": "user@example.com",
                "password_hash": "hash",
                "password_salt": "salt",
                "password_iterations": 1,
                "is_admin": False,
            }
        )
    )

    response = client.post(
        "/register-account",
        data={
            "email": "user@example.com",
            "password": "Secret1234",
            "password_repeat": "Secret1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 409
    assert len(state.users_collection.docs) == 1


def test_login_success(client, state):
    password_data = hash_password("Secret1234")
    run_async(
        state.users_collection.insert_one(
            {
                "email": "user@example.com",
                "is_admin": False,
                **password_data,
            }
        )
    )

    response = client.post(
        "/login",
        data={
            "email": "user@example.com",
            "password": "Secret1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers.get("location") == "/my-registrations"
    assert len(state.sessions_collection.docs) == 1


def test_login_invalid_credentials(client, state):
    password_data = hash_password("Secret1234")
    run_async(
        state.users_collection.insert_one(
            {
                "email": "user@example.com",
                "is_admin": False,
                **password_data,
            }
        )
    )

    response = client.post(
        "/login",
        data={
            "email": "user@example.com",
            "password": "WrongPassword",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert len(state.sessions_collection.docs) == 0
