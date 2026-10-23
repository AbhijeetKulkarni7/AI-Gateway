from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.api_keys import verify_api_key
from app.database import get_db
from app.models import ApiKey, Principal


bearer_scheme = HTTPBearer(
    auto_error=False
)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> Principal:

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication required",
        )

    raw_key = credentials.credentials

    # Expected:
    # aigw_<prefix>_<secret>
    parts = raw_key.split("_", 2)

    if len(parts) != 3 or parts[0] != "aigw":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    prefix = parts[1]

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.prefix == prefix)
        .first()
    )

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if api_key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has been revoked",
        )

    if (
        api_key.expires_at is not None
        and api_key.expires_at <= datetime.now(timezone.utc).replace(
            tzinfo=None
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    if not verify_api_key(
        raw_key,
        api_key.key_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    principal = (
        db.query(Principal)
        .filter(
            Principal.id == api_key.principal_id,
            Principal.is_active.is_(True),
        )
        .first()
    )

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Principal is inactive or missing",
        )

    return principal