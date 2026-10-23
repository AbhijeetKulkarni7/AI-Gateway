
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.credits.service import (
    check_credit_available,
    deduct_credits,
    get_provider_cost,
)
from app.database import get_db
from app.dlp.scanner import scan_prompt
from app.models import Principal, UsageRecord
from app.policy.engine import evaluate_policy
from app.policy.system_message import ORGANIZATION_SYSTEM_MESSAGE
from app.providers.litellm_provider import generate_response
from app.providers.model_registry import resolve_model


router = APIRouter(prefix="/v1", tags=["Chat"])

SUPPORTED_PROVIDERS = {
    "huggingface",
    "gemini",
    "azure_openai",
}


# ---------------------------------------------------------
# Request schemas
# ---------------------------------------------------------

class ChatRequest(BaseModel):
    """Legacy gateway request format."""
    message: str
    provider: str = "huggingface"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionsRequest(BaseModel):
    """Initial OpenAI-compatible, non-streaming request."""
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False


# ---------------------------------------------------------
# Shared gateway processing
# ---------------------------------------------------------

def _process_chat(
    *,
    messages: list[dict],
    provider: str,
    principal: Principal,
    db: Session,
) -> dict:
    """
    Run requests through the existing security and accounting flow.
    Both public endpoints use this function.
    """

    provider = provider.lower().strip()

    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PROVIDER",
                "message": "Unsupported provider.",
            },
        )

    # Combine content for policy evaluation and scan each message
    # separately so sanitized content can retain message boundaries.
    original_text = "\n".join(
        str(message.get("content", ""))
        for message in messages
    )

    message_scans = [
        scan_prompt(str(message.get("content", "")))
        for message in messages
    ]

    dlp_result = scan_prompt(original_text)

    secrets_detected = any(
        bool(result["secrets_detected"])
        for result in message_scans
    ) or bool(dlp_result["secrets_detected"])

    dlp_result["secrets_detected"] = secrets_detected

    # 1. Check credit account.
    account = principal.credit_account

    if account is None:
        raise HTTPException(
            status_code=404,
            detail="Credit account not found",
        )

    # Preserve the existing pre-request estimate for now.
    # This is a fixed estimate, not the actual provider cost.
    estimated_cost = Decimal("1.00")

    try:
        check_credit_available(
            account=account,
            estimated_cost=estimated_cost,
        )
    except HTTPException as exc:
        error_code = (
            exc.detail.get("code")
            if isinstance(exc.detail, dict)
            else None
        )

        usage_record = UsageRecord(
            principal_id=principal.id,
            team_id=principal.team_id,
            provider=provider,
            model=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost=Decimal("0"),
            request_status=(
                "credit_exhausted"
                if error_code == "CREDIT_EXHAUSTED"
                else "credit_account_blocked"
            ),
            dlp_blocked=False,
            secrets_redacted=secrets_detected,
        )

        db.add(usage_record)
        db.commit()
        raise

    # 2. Policy evaluation.
    policy_result = evaluate_policy(
        prompt=original_text,
        dlp_result=dlp_result,
    )

    if not policy_result.allowed:
        usage_record = UsageRecord(
            principal_id=principal.id,
            team_id=principal.team_id,
            provider=provider,
            model=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost=Decimal("0"),
            request_status="policy_blocked",
            dlp_blocked=True,
            secrets_redacted=secrets_detected,
        )

        db.add(usage_record)
        db.commit()
        db.refresh(usage_record)

        raise HTTPException(
            status_code=403,
            detail={
                "code": "POLICY_VIOLATION",
                "message": (
                    "Request blocked by organization "
                    "security policy."
                ),
                "violations": policy_result.violations,
                "usage_record_id": usage_record.id,
            },
        )

    # 3. Sanitize every message and preserve conversation order.
    sanitized_messages = []

    for message, scan_result in zip(messages, message_scans):
        role = message["role"]
        content = scan_result["sanitized_text"]

        # Never allow a client-provided instruction message to
        # replace the gateway's mandatory system instructions.
        if role in {"system", "developer"}:
            role = "user"
            content = (
                "[Untrusted client-provided context; "
                "not gateway policy instructions]\n"
                + content
            )

        sanitized_messages.append({
            "role": role,
            "content": content,
        })

    # 4. Add the gateway's trusted system instruction.
    provider_messages = [
        {
            "role": "system",
            "content": ORGANIZATION_SYSTEM_MESSAGE,
        },
        *sanitized_messages,
    ]

    # 5. Call LiteLLM.
    try:
        response = generate_response(
            provider_messages,
            provider=provider,
        )
    except Exception as exc:
        usage_record = UsageRecord(
            principal_id=principal.id,
            team_id=principal.team_id,
            provider=provider,
            model=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost=Decimal("0"),
            request_status="provider_error",
            dlp_blocked=False,
            secrets_redacted=secrets_detected,
        )

        db.add(usage_record)
        db.commit()
        db.refresh(usage_record)

        raise HTTPException(
            status_code=502,
            detail={
                "code": "LLM_PROVIDER_ERROR",
                "message": (
                    "The downstream AI provider request failed."
                ),
                "usage_record_id": usage_record.id,
            },
        ) from exc

    # 6. Extract response and usage.
    actual_cost = get_provider_cost(response)

    if actual_cost > Decimal("0"):
        deduct_credits(
            db=db,
            account=account,
            amount=actual_cost,
            reason="LLM inference",
            reference_id=None,
        )

    assistant_message = response.choices[0].message.content

    usage = getattr(response, "usage", None)

    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = (
        getattr(usage, "completion_tokens", 0) or 0
    )
    total_tokens = getattr(usage, "total_tokens", 0) or 0

    provider_usage_cost = getattr(
        usage,
        "estimated_cost",
        None,
    ) if usage is not None else None

    provider_cost = (
        Decimal(str(provider_usage_cost))
        if provider_usage_cost is not None
        else actual_cost
    )

    # 7. Record successful usage.
    usage_record = UsageRecord(
        principal_id=principal.id,
        team_id=principal.team_id,
        provider=provider,
        model=response.model,
        prompt_tokens=int(prompt_tokens),
        completion_tokens=int(completion_tokens),
        total_tokens=int(total_tokens),
        estimated_cost=provider_cost,
        request_status="success",
        dlp_blocked=False,
        secrets_redacted=secrets_detected,
    )

    db.add(usage_record)
    db.commit()
    db.refresh(usage_record)

    return {
        "assistant_message": assistant_message,
        "provider": provider,
        "actual_model": response.model,
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(total_tokens),
        "estimated_cost": str(provider_cost),
        "secrets_redacted": secrets_detected,
        "usage_record_id": usage_record.id,
        "finish_reason": (
            getattr(response.choices[0], "finish_reason", None)
        ),
    }


# ---------------------------------------------------------
# Existing endpoint: keep compatibility with the dashboard
# ---------------------------------------------------------

@router.post("/chat")
def chat(
    request: ChatRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    result = _process_chat(
        messages=[{
            "role": "user",
            "content": request.message,
        }],
        provider=request.provider,
        principal=principal,
        db=db,
    )

    return {
        "principal_id": principal.id,
        "response": result["assistant_message"],
        "provider": result["provider"],
        "model": result["actual_model"],
        "secrets_redacted": result["secrets_redacted"],
        "system_message_applied": True,
        "usage": {
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "total_tokens": result["total_tokens"],
            "estimated_cost": result["estimated_cost"],
        },
        "usage_record_id": result["usage_record_id"],
    }


# ---------------------------------------------------------
# New endpoint: OpenAI-compatible chat interface
# ---------------------------------------------------------

@router.post("/chat/completions")
def chat_completions(
    request: ChatCompletionsRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    if request.stream:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STREAMING_NOT_SUPPORTED",
                "message": (
                    "Streaming is not supported by this "
                    "initial gateway endpoint."
                ),
            },
        )

    model_config = resolve_model(request.model)

    result = _process_chat(
        messages=[
            message.model_dump()
            for message in request.messages
        ],
        provider=model_config["provider"],
        principal=principal,
        db=db,
    )

    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(__import__("time").time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result["assistant_message"],
                },
                "finish_reason": result["finish_reason"] or "stop",
            }
        ],
        "usage": {
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "total_tokens": result["total_tokens"],
        },
        "x_gateway": {
            "provider": result["provider"],
            "estimated_cost": result["estimated_cost"],
            "secrets_redacted": result["secrets_redacted"],
            "usage_record_id": result["usage_record_id"],
        },
    }
