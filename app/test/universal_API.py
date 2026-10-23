
from openai import OpenAI, APIStatusError

client = OpenAI(
    api_key="aigw_8dac4ffa_9Bk0NSLCRTgO3RZnqD15rAhTMWu9cfEH",
    base_url="http://127.0.0.1:8000/v1",
)

try:
    response = client.chat.completions.create(
        model="company-chat-azure",
        messages=[
            {
                "role": "user",
                "content": (
                    "Write a Python function to check whether "
                    "a number is prime. Explain it briefly."
                ),
            }
        ],
    )

    print("Model:", response.model)
    print("Answer:")
    print(response.choices[0].message.content)
    print("Usage:", response.usage)
    print("##########################################")
    print(response.json())

except APIStatusError as exc:
    print("HTTP status:", exc.status_code)
    print("Gateway error:", exc.response.text)
