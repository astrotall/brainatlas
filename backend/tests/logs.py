import pytest


def logged_text(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(f"{record.getMessage()} {record.__dict__}" for record in caplog.records)
