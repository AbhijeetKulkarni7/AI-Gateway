from app.dlp.scanner import scan_prompt

tests = [
    "Can confidential information be processed by an external AI provider without approval?",
    "Classification: Confidential",
    "CONFIDENTIAL: Internal employee records",
]

for prompt in tests:
    result = scan_prompt(prompt)
    print("\nPrompt:", prompt)
    print("Sensitive detected:", result["sensitive_data_detected"])
    print("Matching types:", [
        finding["type"]
        for finding in result["sensitive_findings"]
    ])