import sqlite3


DB_PATH = "gateway.db"


def test_usage_records_table_exists():
    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = 'usage_records';
    """)

    result = cursor.fetchone()

    connection.close()

    assert result is not None, (
        "usage_records table does not exist"
    )


def test_usage_records_schema():
    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    cursor.execute(
        "PRAGMA table_info(usage_records);"
    )

    columns = cursor.fetchall()

    connection.close()

    column_names = [
        column[1]
        for column in columns
    ]

    expected_columns = [
        "id",
        "principal_id",
        "team_id",
        "provider",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost",
        "request_status",
        "dlp_blocked",
        "secrets_redacted",
        "created_at",
    ]

    for column in expected_columns:
        assert column in column_names, (
            f"Missing column: {column}"
        )


def test_usage_records_can_be_read():
    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            principal_id,
            team_id,
            provider,
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            estimated_cost,
            request_status,
            dlp_blocked,
            secrets_redacted,
            created_at
        FROM usage_records;
    """)

    rows = cursor.fetchall()

    connection.close()

    print(
        f"\nUsage records found: {len(rows)}"
    )

    for row in rows:
        print(row)

    assert rows is not None