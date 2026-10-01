from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_does_not_store_plaintext():
    encoded = hash_password("a-strong-password")
    assert encoded != "a-strong-password"
    assert verify_password("a-strong-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_jwt_round_trip():
    token = create_access_token("subject-123")
    assert decode_access_token(token) == "subject-123"
