from huggingface_hub import InferenceClient
from app.config import settings


def test_huggingface_direct():
    client = InferenceClient(
        api_key=settings.huggingface_api_key,
        provider="auto",
    )

    response = client.chat.completions.create(
        model=settings.huggingface_model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful enterprise AI assistant.",
            },
            {
                "role": "user",
                "content": "Explain what an API is in one sentence.",
            },
        ],
        max_tokens=100,
        temperature=0.2,
    )

    print("\nMODEL:", response.model)
    print("RESPONSE:", response.choices[0].message.content)
    print("USAGE:", response.usage)

    assert response.choices
    assert response.choices[0].message.content