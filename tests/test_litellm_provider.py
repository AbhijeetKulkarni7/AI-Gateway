from app.providers.litellm_provider import generate_response


def test_huggingface_llm():
    messages = [
        {
            "role": "system",
            "content": "You are a helpful enterprise AI assistant.",
        },
        {
            "role": "user",
            "content": "Explain what an API is in one sentence.",
        },
    ]

    response = generate_response(messages)

    assert response is not None
    assert response.choices
    assert response.choices[0].message.content