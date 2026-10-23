
from app.providers.litellm_provider import generate_response


def main():
    response = generate_response(
        messages=[
            {
                "role": "user",
                "content": (
                    "Write a Python function to reverse a string. "
                    "Explain the code briefly."
                ),
            }
        ],
        provider="azure_openai",
    )

    print("\n========== AZURE OPENAI RESPONSE ==========")
    print(response.choices[0].message.content)
    print("Model:", response.model)

    if response.usage:
        print("Prompt tokens:", response.usage.prompt_tokens)
        print("Completion tokens:", response.usage.completion_tokens)
        print("Total tokens:", response.usage.total_tokens)

    print("===========================================")


if __name__ == "__main__":
    main()
