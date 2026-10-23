from app.dlp.detectors import SECRET_PATTERNS, SENSITIVE_PATTERNS


REDACTION_TEXT = "[REDACTED]"


def detect_secrets(text: str) -> list[dict]:
    findings = []

    for name, pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append(
                {
                    "type": name,
                    "category": "secret",
                    "start": match.start(),
                    "end": match.end(),
                    "value": match.group(0),
                }
            )

    return findings


def detect_sensitive_data(text: str) -> list[dict]:
    findings = []

    for name, pattern in SENSITIVE_PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append(
                {
                    "type": name,
                    "category": "sensitive",
                    "start": match.start(),
                    "end": match.end(),
                    "value": match.group(0),
                }
            )

    return findings

def redact_secrets(text: str) -> tuple[str, list[dict]]:
    findings = detect_secrets(text)

    redacted_text = text

    for finding in findings:
        pattern = SECRET_PATTERNS[finding["type"]]

        redacted_text = pattern.sub(
            REDACTION_TEXT,
            redacted_text,
        )

    return redacted_text, findings

# Main DLP SCAN 

def scan_prompt(text: str) -> dict:
    secret_findings = detect_secrets(text)
    sensitive_findings = detect_sensitive_data(text)

    redacted_text = text

    if secret_findings:
        redacted_text, _ = redact_secrets(text)

    return {
        "original_text": text,
        "sanitized_text": redacted_text,
        "secrets_detected": len(secret_findings) > 0,
        "sensitive_data_detected": len(sensitive_findings) > 0,
        "secret_findings": secret_findings,
        "sensitive_findings": sensitive_findings,
        "blocked": len(sensitive_findings) > 0,
    }

