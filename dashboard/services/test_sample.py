from api_client import APIClient


api_client = APIClient(
    base_url="http://127.0.0.1:8000",
    admin_key="dev-admin-key-12345",
)


data = api_client.get_principals(
    page=1,
    page_size=10,
    search="Abhijeet",
)


print(data)