# PulseAI

A Claude Code routine that researches AI and software every day, verifies what it finds against
primary sources, and publishes one visual, consistently designed report.

Status: under construction (milestone M1, foundation). See
`docs/superpowers/specs/2026-10-11-pulseai-daily-research-routine-design.md`.

## Development

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js LTS, pnpm (via Corepack).

    uv sync
    pnpm install
    uv run pytest
    pnpm test
    uv run pre-commit install
