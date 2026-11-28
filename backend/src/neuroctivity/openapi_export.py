import json
import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from neuroctivity.main import create_app

CHECK_FLAG = "--check"
STALE_MESSAGE = "error: the committed OpenAPI schema is stale; run 'make openapi' and commit the result\n"


def render_schema() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(arguments: Sequence[str]) -> int:
    parser = ArgumentParser(prog="openapi_export")
    parser.add_argument("path", type=Path)
    parser.add_argument(CHECK_FLAG, action="store_true")
    options = parser.parse_args(arguments)
    path: Path = options.path
    check: bool = options.check
    schema = render_schema()
    if not check:
        path.write_text(schema, encoding="utf-8", newline="\n")
        return 0
    if path.is_file() and path.read_bytes() == schema.encode():
        return 0
    sys.stderr.write(STALE_MESSAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
