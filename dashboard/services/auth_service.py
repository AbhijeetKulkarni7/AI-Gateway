from services.api_client import APIClient


def authenticate_user(
    base_url: str,
    api_key: str,
):
    """
    Authenticate a normal user using the existing
    FastAPI /v1/whoami endpoint.
    """

    client = APIClient(
        base_url=base_url,
        api_key=api_key,
    )

    user = client.get_current_user()

    return client, user


def authenticate_admin(
    base_url: str,
    admin_key: str,
):
    """
    Authenticate an administrator using the existing
    X-Admin-Key protected endpoint.
    """

    client = APIClient(
        base_url=base_url,
        admin_key=admin_key,
    )

    # Existing Admin API is used to validate the admin key.
    client.validate_admin()

    return client