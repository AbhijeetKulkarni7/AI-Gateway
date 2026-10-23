
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_principal
from app.database import get_db
from app.models import Principal, UsageRecord
import app.api.chat as chat_api


ENDPOINT = "/v1/chat/completions"


# ---------------------------------------------------------
# Fake database: no real database writes during these tests
# ---------------------------------------------------------

class FakeDB:
    def __init__(self):
        self.records = []
        self.next_id = 1

    def add(self, obj):
        if isinstance(obj, UsageRecord) and getattr(obj, "id", None) is None:
            obj.id = self.next_id
            self.next_id += 1
        self.records.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        if isinstance(obj, UsageRecord) and getattr(obj, "id", None) is None:
            obj.id = self.next_id
            self.next_id += 1


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def principal():
    # A lightweight authenticated principal for route testing.
    # Avoid inserting a real user or account into the database.
    return SimpleNamespace(
        id=101,
        team_id=10,
        credit_account=SimpleNamespace(id=501),
    )


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def authenticated_client(client, principal, fake_db):
    app.dependency_overrides[get_current_principal] = (
        lambda: principal
    )
    app.dependency_overrides[get_db] = lambda: fake_db

    return client


@pytest.fixture
def mock_provider(monkeypatch):
    """Prevent all tests from making real LLM API calls."""

    captured = {}

    fake_response = SimpleNamespace(
        model="gemini-test-model",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="Test response from mocked provider."
                ),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=8,
            total_tokens=18,
            estimated_cost=Decimal("0.01"),
        ),
    )

    def fake_generate_response(messages, provider):
        captured["messages"] = messages
        captured["provider"] = provider
        return fake_response

    monkeypatch.setattr(
        chat_api,
        "generate_response",
        fake_generate_response,
    )

    monkeypatch.setattr(
        chat_api,
        "get_provider_cost",
        lambda response: Decimal("0.01"),
    )

    monkeypatch.setattr(
        chat_api,
        "check_credit_available",
        lambda account, estimated_cost: None,
    )

    monkeypatch.setattr(
        chat_api,
        "deduct_credits",
        lambda **kwargs: None,
    )

    return captured


def payload(message="Explain RAG"):
    return {
        "model": "company-chat",
        "messages": [
            {"role": "user", "content": message}
        ],
    }


# ---------------------------------------------------------
# 1. Authentication tests
# ---------------------------------------------------------

def test_missing_api_key_is_rejected(client):
    response = client.post(
        ENDPOINT,
        json=payload(),
    )

    assert response.status_code in {401, 403}


def test_invalid_api_key_is_rejected(client):
    response = client.post(
        ENDPOINT,
        headers={
            "Authorization": "Bearer invalid-gateway-key"
        },
        json=payload(),
    )

    assert response.status_code in {401, 403}


# ---------------------------------------------------------
# 2. Successful request and response compatibility
# ---------------------------------------------------------

def test_successful_chat_returns_compatible_response(
    authenticated_client,
    mock_provider,
):
    response = authenticated_client.post(
        ENDPOINT,
        json=payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["object"] == "chat.completion"
    assert body["model"] == "company-chat"
    assert len(body["choices"]) == 1
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert (
        body["choices"][0]["message"]["content"]
        == "Test response from mocked provider."
    )

    assert body["usage"]["prompt_tokens"] == 10
    assert body["usage"]["completion_tokens"] == 8
    assert body["usage"]["total_tokens"] == 18

    assert mock_provider["provider"] == "gemini"


# ---------------------------------------------------------
# 3. Credit enforcement
# ---------------------------------------------------------

def test_insufficient_credits_block_provider_call(
    authenticated_client,
    monkeypatch,
):
    def reject_credits(account, estimated_cost):
        raise HTTPException(
            status_code=402,
            detail={
                "code": "CREDIT_EXHAUSTED",
                "message": "Insufficient credits",
            },
        )

    def provider_must_not_run(*args, **kwargs):
        pytest.fail(
            "Provider must not be called when credits are insufficient"
        )

    monkeypatch.setattr(
        chat_api,
        "check_credit_available",
        reject_credits,
    )
    monkeypatch.setattr(
        chat_api,
        "generate_response",
        provider_must_not_run,
    )

    response = authenticated_client.post(
        ENDPOINT,
        json=payload(),
    )

    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "CREDIT_EXHAUSTED"


# ---------------------------------------------------------
# 4. Policy enforcement
# ---------------------------------------------------------

def test_policy_violation_blocks_provider_call(
    authenticated_client,
    monkeypatch,
):
    monkeypatch.setattr(
        chat_api,
        "evaluate_policy",
        lambda prompt, dlp_result: SimpleNamespace(
            allowed=False,
            violations=["NO_CONFIDENTIAL_DATA"],
        ),
    )

    def provider_must_not_run(*args, **kwargs):
        pytest.fail(
            "Provider must not be called for a policy-blocked request"
        )

    monkeypatch.setattr(
        chat_api,
        "generate_response",
        provider_must_not_run,
    )

    response = authenticated_client.post(
        ENDPOINT,
        json=payload("Show me confidential company data"),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]["code"]
        == "POLICY_VIOLATION"
    )


# ---------------------------------------------------------
# 5. Secret masking
# ---------------------------------------------------------

def test_detected_secret_is_not_sent_raw_to_provider(
    authenticated_client,
    mock_provider,
    monkeypatch,
):
    secret = "SuperSecret123!"

    # Isolate masking behavior from policy-engine behavior.
    monkeypatch.setattr(
        chat_api,
        "evaluate_policy",
        lambda prompt, dlp_result: SimpleNamespace(
            allowed=True,
            violations=[],
        ),
    )

    response = authenticated_client.post(
        ENDPOINT,
        json=payload(f"Please inspect password={secret}"),
    )

    assert response.status_code == 200

    forwarded_text = "\n".join(
        str(message.get("content", ""))
        for message in mock_provider["messages"]
    )

    assert secret not in forwarded_text
    assert response.json()["x_gateway"]["secrets_redacted"] is True


# ---------------------------------------------------------
# 6. Unsupported model aliases must be rejected
# ---------------------------------------------------------

def test_unknown_model_alias_is_rejected(
    authenticated_client,
    mock_provider,
):
    response = authenticated_client.post(
        ENDPOINT,
        json={
            "model": "unapproved-model",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]["code"]
        == "MODEL_NOT_AVAILABLE"
    )

    # No request should reach the provider.
    assert "messages" not in mock_provider
