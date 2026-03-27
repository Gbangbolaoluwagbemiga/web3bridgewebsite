from app.core.security import (
    TokenType,
    create_activation_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_roundtrip() -> None:
    password = "SuperSecure123"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_activation_token_roundtrip() -> None:
    token, _, _ = create_activation_token(user_id=42, email="student@example.com")
    payload = decode_token(token, expected_type=TokenType.ACTIVATION)

    assert payload["sub"] == "42"
    assert payload["email"] == "student@example.com"
    assert payload["type"] == TokenType.ACTIVATION
