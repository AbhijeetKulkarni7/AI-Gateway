import re


SECRET_PATTERNS = {
    "password": re.compile(
    r"""(?i)\b(password|passwd|pwd)\s*(?:[:=]\s*|is\s+)(["']?)([^\s"']+)\2"""
),

    "api_key": re.compile(
        r"(?i)\b(api[_-]?key|apikey)\s*[:=]\s*[\"']?([A-Za-z0-9_\-]{12,})"
    ),

    "jwt": re.compile(
        r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    ),

    "aws_access_key": re.compile(
        r"\bAKIA[0-9A-Z]{16}\b"
    ),

    "private_key": re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),

    "database_url": re.compile(
        r"(?i)\b(?:postgresql|postgres|mysql|mongodb(?:\+srv)?)://[^\s]+"
    ),
}

SENSITIVE_PATTERNS = {
    "internal_confidential": re.compile(
        r"(?im)(?:^|[\n;])[ \t]*"
        r"(?:(?:classification|sensitivity|data classification)"
        r"[ \t]*[:=][ \t]*)?"
        r"(?:strictly[ \t]+confidential|"
        r"company[ \t]+confidential|"
        r"confidential|"
        r"internal[ \t]+use[ \t]+only|"
        r"proprietary[ \t]+information|"
        r"trade[ \t]+secret)"
        r"(?:[ \t]*[:|—-][ \t]*\S.*|[ \t]*$)"
    ),

    "production_information": re.compile(
        r"(?i)\b("
        r"production database|"
        r"prod database|"
        r"production server|"
        r"prod server|"
        r"production credentials|"
        r"production password"
        r")\b"
    ),

    "customer_data": re.compile(
        r"(?i)\b("
        r"customer database|"
        r"customer records|"
        r"customer information|"
        r"client database|"
        r"client records"
        r")\b"
    ),
}

