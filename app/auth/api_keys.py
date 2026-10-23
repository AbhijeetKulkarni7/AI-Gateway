import hashlib
import hmac
import secrets


KEY_PREFIX = "aigw"


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate an API key.

    Returns:
        raw_key: Full API key returned to the caller once.
        prefix: Public lookup prefix.
        key_hash: SHA-256 hash stored in the database.
    """

    prefix = secrets.token_hex(4)

    # 24 bytes gives us a 32-character URL-safe secret.
    secret = secrets.token_urlsafe(24)

    raw_key = f"{KEY_PREFIX}_{prefix}_{secret}"

    key_hash = hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()

    return raw_key, prefix, key_hash


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    incoming_hash = hash_api_key(api_key)

    return hmac.compare_digest(
        incoming_hash,
        stored_hash,
    )