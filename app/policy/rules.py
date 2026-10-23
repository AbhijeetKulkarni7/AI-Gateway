DEFAULT_POLICIES = [
    {
        "code": "NO_CREDENTIAL_EXPOSURE",
        "description": "Credentials and secrets must not be exposed.",
        "action": "deny",
    },
    {
        "code": "NO_CONFIDENTIAL_DATA",
        "description": "Confidential organizational information must not be sent to external AI models.",
        "action": "deny",
    },
    {
        "code": "NO_PERSONAL_DATA",
        "description": "Personal information should not be intentionally exposed.",
        "action": "deny",
    },
]