from litellm import completion
from app.config import settings


def generate_response(messages, provider="huggingface"):
    try:
        api_base = None
        api_version = None

        if provider == "gemini":
            model = f"gemini/{settings.gemini_model}"
            api_key = settings.gemini_api_key

        elif provider == "huggingface":
            model = f"huggingface/{settings.huggingface_model}"
            api_key = settings.huggingface_api_key

        elif provider == "azure_openai":
            model = f"azure/{settings.azure_openai_deployment}"
            api_key = settings.azure_openai_api_key
            api_base = settings.azure_openai_endpoint
            api_version = settings.azure_openai_api_version

        else:
            raise ValueError(
                f"Unsupported LLM provider: {provider}"
            )

        if not api_key:
            raise RuntimeError(
                f"API key is not configured for provider: {provider}"
            )

        print("\n========== LITELLM REQUEST ==========")
        print(f"Provider: {provider}")
        print(f"Model: {model}")
        print("=====================================\n")

        request_kwargs = {
            "model": model,
            "messages": messages,
            "api_key": api_key,
            "max_tokens": 1000,
            "temperature": 0.2,
            "num_retries": 1,
            "timeout": 60,
        }

        if provider == "azure_openai":
            if not api_base or not api_version:
                raise RuntimeError(
                    "Azure OpenAI endpoint or API version is missing."
                )

            request_kwargs["api_base"] = api_base
            request_kwargs["api_version"] = api_version

        return completion(**request_kwargs)

    except Exception as exc:
        # Never log API keys or full prompt content.
        print("\n========== LITELLM PROVIDER ERROR ==========")
        print(f"Provider: {provider}")
        print(f"Error type: {type(exc).__name__}")
        print(f"Error details: {exc!s}")
        print("============================================")
        raise