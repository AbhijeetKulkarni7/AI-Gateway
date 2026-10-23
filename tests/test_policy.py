from app.dlp.scanner import scan_prompt
from app.policy.engine import evaluate_policy


def test_normal_prompt_allowed():
    prompt = "Explain transformers."

    dlp_result = scan_prompt(prompt)
    result = evaluate_policy(prompt, dlp_result)

    assert result.allowed is True
    assert result.violations == []


def test_secret_is_redacted_not_blocked():
    prompt = "My password is SuperSecret123"

    dlp_result = scan_prompt(prompt)
    result = evaluate_policy(prompt, dlp_result)

    assert result.allowed is True
    assert any(
        v["code"] == "NO_CREDENTIAL_EXPOSURE"
        for v in result.violations
    )


def test_sensitive_information_denied():
    prompt = "The production database contains customer records."

    dlp_result = scan_prompt(prompt)
    result = evaluate_policy(prompt, dlp_result)

    assert result.allowed is False
    assert any(
        v["action"] == "deny"
        for v in result.violations
    )