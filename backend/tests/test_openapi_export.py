import json
from pathlib import Path

import pytest

from neuroctivity.openapi_export import main, render_schema
from tests.transport.openapi import SCHEMA_PATH


def test_the_committed_schema_matches_the_code() -> None:
    assert SCHEMA_PATH.read_bytes() == render_schema().encode()


def test_renders_deterministically_with_sorted_keys() -> None:
    rendered = render_schema()

    assert rendered == render_schema()
    assert rendered == json.dumps(json.loads(rendered), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_writes_the_schema_and_then_passes_its_own_check(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"

    assert main([str(target)]) == 0
    assert main(["--check", str(target)]) == 0
    assert target.read_bytes() == render_schema().encode()


@pytest.mark.parametrize("stale", [None, "", "{}\n", "trailing"])
def test_the_check_fails_on_a_missing_or_stale_file_and_leaves_it_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], stale: str | None
) -> None:
    target = tmp_path / "openapi.json"
    if stale is not None:
        content = f"{render_schema()}\n" if stale == "trailing" else stale
        target.write_text(content, encoding="utf-8")
    before = target.read_bytes() if target.exists() else None

    assert main(["--check", str(target)]) == 1
    assert "make openapi" in capsys.readouterr().err
    assert (target.read_bytes() if target.exists() else None) == before
