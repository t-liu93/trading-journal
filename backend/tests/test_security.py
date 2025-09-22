from trading_journal import security


def test_hash_and_verify_password() -> None:
    plain = "password"
    hashed = security.hash_password(plain)
    assert hashed != plain
    assert security.verify_password(plain, hashed)


def test_generate_session_token() -> None:
    token1 = security.generate_session_token()
    token2 = security.generate_session_token()
    assert token1 != token2
    assert len(token1) > 0
    assert len(token2) > 0


def test_hash_and_verify_session_token_sha256() -> None:
    token = security.generate_session_token()
    token_hash = security.hash_session_token_sha256(token)
    assert token_hash != token
    assert security.verify_token_sha256(token, token_hash)
    assert not security.verify_token_sha256(token + "x", token_hash)
