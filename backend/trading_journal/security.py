import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

import settings

ph = PasswordHasher()

# Utility functions for password hashing and verification


def hash_password(plain: str) -> str:
    return ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


# Session token hash


def generate_session_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_session_token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sign_token_hmac(token: str) -> str:
    if not settings.settings.hmac_key:
        return token
    return hmac.new(settings.settings.hmac_key.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_token_sha256(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_session_token_sha256(token), expected_hash)


def verify_token_hmac(token: str, expected_hmac: str) -> bool:
    if not settings.settings.hmac_key:
        return verify_token_sha256(token, expected_hmac)
    sig = hmac.new(settings.settings.hmac_key.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected_hmac)
