from services.auth_service import authenticate_user


BASE_URL = "http://127.0.0.1:8000"

api_key = input("Enter API key: ").strip()

try:

    client, user = authenticate_user(
        BASE_URL,
        api_key,
    )

    print("\nAuthentication successful!")
    print(user)

except Exception as exc:

    print("\nAuthentication failed!")
    print(type(exc).__name__)
    print(exc)