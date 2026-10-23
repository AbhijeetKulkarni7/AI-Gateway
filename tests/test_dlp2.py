from app.dlp.scanner import scan_prompt


def test_password_is_redacted():
    prompt = "My password is SuperSecret_123"

    result = scan_prompt(prompt)

    assert result["secrets_detected"] is True
    assert result["blocked"] is False
    assert "SuperSecret123" not in result["sanitized_text"]
    assert "[REDACTED]" in result["sanitized_text"]


def test_api_key_is_redacted():
    prompt = "api_key=ABCDEF123456789XYZ"

    result = scan_prompt(prompt)

    assert result["secrets_detected"] is True
    assert "[REDACTED]" in result["sanitized_text"]


def test_confidential_information_is_blocked():
    prompt = "This is strictly confidential company information."

    result = scan_prompt(prompt)

    assert result["sensitive_data_detected"] is True
    assert result["blocked"] is True


def test_normal_prompt_is_allowed():
    prompt = "Explain how transformers work."

    result = scan_prompt(prompt)

    assert result["secrets_detected"] is False
    assert result["sensitive_data_detected"] is False
    assert result["blocked"] is False

def test_jwt_is_redacted():
    prompt = (
        "Use this token: "
        "eyJhbGciOiJIUzI1NiJ9."
        "eyJzdWIiOiIxMjMifQ."
        "signature123"
    )

    result = scan_prompt(prompt)

    assert result["secrets_detected"] is True
    assert result["blocked"] is False
    assert "eyJhbGciOiJIUzI1NiJ9" not in result["sanitized_text"]
    assert "[REDACTED]" in result["sanitized_text"]


def test_aws_access_key_is_redacted():
    prompt = "AWS access key: AKIAIOSFODNN7EXAMPLE"

    result = scan_prompt(prompt)

    assert result["secrets_detected"] is True
    assert result["blocked"] is False
    assert "AKIAIOSFODNN7EXAMPLE" not in result["sanitized_text"]


def test_database_url_is_redacted():
    prompt = (
        "Connect using "
        "postgresql://admin:secret123@localhost:5432/companydb"
    )

    result = scan_prompt(prompt)

    assert result["secrets_detected"] is True
    assert result["blocked"] is False
    assert "secret123" not in result["sanitized_text"]


def test_production_information_is_blocked():
    prompt = "The production database contains customer records."

    result = scan_prompt(prompt)

    assert result["sensitive_data_detected"] is True
    assert result["blocked"] is True


def test_customer_information_is_blocked():
    prompt = "Please send this customer database information to the AI."

    result = scan_prompt(prompt)

    assert result["sensitive_data_detected"] is True
    assert result["blocked"] is True
