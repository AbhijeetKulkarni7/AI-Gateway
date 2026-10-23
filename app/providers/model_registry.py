# app/providers/model_registry.py

MODEL_REGISTRY = {
    "company-chat": {
        "provider": "gemini",
    },
    "company-chat-hf": {
        "provider": "huggingface",
    },
     "company-chat-azure": {
        "provider": "azure_openai"
    },
}


def resolve_model(model_name: str) -> dict:
    """Resolve a public model alias to an approved provider."""

    model_name = model_name.strip()

    model_config = MODEL_REGISTRY.get(model_name)

    if model_config is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail={
                "code": "MODEL_NOT_AVAILABLE",
                "message": (
                    f"Model '{model_name}' is not available "
                    "through this gateway."
                ),
            },
        )

    return {
        "model": model_name,
        "provider": model_config["provider"],
    }