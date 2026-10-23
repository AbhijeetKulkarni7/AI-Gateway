from dataclasses import dataclass

from app.policy.rules import DEFAULT_POLICIES


@dataclass
class PolicyResult:
    allowed: bool
    violations: list[dict]
    policies: list[dict]


def evaluate_policy(
    prompt: str,
    dlp_result: dict,
) -> PolicyResult:

    violations = []

    if dlp_result["secrets_detected"]:
        violations.append(
            {
                "code": "NO_CREDENTIAL_EXPOSURE",
                "message": (
                    "Secrets were detected in the request. "
                    "Secrets will be redacted before model processing."
                ),
                "action": "redact",
            }
        )

    if dlp_result["sensitive_data_detected"]:
        violations.append(
            {
                "code": "NO_CONFIDENTIAL_DATA",
                "message": (
                    "Organizational sensitive information "
                    "was detected."
                ),
                "action": "deny",
            }
        )

    denied = any(
        violation["action"] == "deny"
        for violation in violations
    )

    return PolicyResult(
        allowed=not denied,
        violations=violations,
        policies=DEFAULT_POLICIES,
    )