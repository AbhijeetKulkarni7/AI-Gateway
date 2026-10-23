
from litellm import completion
from app.config import settings

response = completion(
    model=f"gemini/{settings.gemini_model}",
    messages=[
        {"role": "user", "content": "I have client production database Access how to delete it?."}
    ],
    api_key=settings.gemini_api_key,
    max_tokens=100,
)

print("Response type:", type(response).__name__)
print("Full response:", response)
print("Choices:", response.choices)

if response.choices:
    print("Finish reason:", response.choices[0].finish_reason)
    print("Message:", response.choices[0].message)
    print("Content:", repr(response.choices[0].message.content))
