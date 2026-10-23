from openai import OpenAI

client = OpenAI(
    api_key="aigw_b11a352d_gaZuVUPNKaUG8ZzyXBMewKuXAZeQosSu",
    base_url="http://127.0.0.1:8000/v1",
)

response = client.chat.completions.create(
    model="company-chat-azure",
    messages=[
        {
            "role": "user",
            "content": "Explain Attention mechanism in two lines.",
        }
    ],
)

print("Answer:", response.choices[0].message.content)
print("Usage:", response.usage)