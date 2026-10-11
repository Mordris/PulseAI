"""Generate Pydantic models from schema/*.schema.json, the single source of truth.

Usage:
    uv run python scripts/generate_models.py          # write models
    uv run python scripts/generate_models.py --check  # fail if models are stale
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema"
OUT_DIR = ROOT / "packages" / "cli" / "src" / "pulseai" / "models"
INIT_TEXT = (
    '"""Pydantic models generated from schema/*.schema.json. '
    'Do not edit; run scripts/generate_models.py."""\n'
)
FLAGS = [
    "--input-file-type", "jsonschema",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--target-python-version", "3.12",
    "--use-standard-collections",
    "--use-union-operator",
    "--field-constraints",
    "--use-annotated",
    "--enum-field-as-literal", "all",
    "--use-double-quotes",
    "--disable-timestamp",
    "--use-title-as-name",
    "--use-schema-description",
    "--use-type-alias",
    # Keep timestamps as str: their pattern (uppercase T and Z, see report.schema.json) cannot be
    # applied to pydantic's datetime types.
    "--type-mappings", "string+date-time=string",
    "--formatters", "builtin",
]  # fmt: skip


def module_name(schema: Path) -> str:
    return schema.name.removesuffix(".schema.json").replace("-", "_")


def generate(schema: Path, check: bool) -> str | None:
    out = OUT_DIR / f"{module_name(schema)}.py"
    cmd = [sys.executable, "-m", "datamodel_code_generator", "--input", str(schema)]
    cmd += ["--output", str(out), *FLAGS]
    if check:
        cmd.append("--check")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return f"{schema.name}: {result.stderr.strip() or result.stdout.strip()}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify models are up to date")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    problems = [
        p for s in sorted(SCHEMA_DIR.glob("*.schema.json")) if (p := generate(s, args.check))
    ]

    init = OUT_DIR / "__init__.py"
    if args.check:
        if not init.is_file() or init.read_text(encoding="utf-8") != INIT_TEXT:
            problems.append("models/__init__.py is out of date")
    else:
        init.write_text(INIT_TEXT, encoding="utf-8")

    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
