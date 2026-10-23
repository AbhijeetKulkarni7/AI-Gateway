from services.api_client import APIClient


API_KEY = "aigw_01e62519_ew09dSy-R25Iu58b6Qog1M9V0n1dDYna"


def main():
    client = APIClient(
        base_url="http://127.0.0.1:8000",
        api_key=API_KEY,
    )

    balance = client.get_credit_balance()

    print("Credit Balance:")
    print(balance)


if __name__ == "__main__":
    main()