#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$script_dir/.."

uv sync --locked --extra dev --no-editable
uv run --no-sync ruff check .
uv run --no-sync pytest -q
uv run --no-sync synapse smoke
uv build
