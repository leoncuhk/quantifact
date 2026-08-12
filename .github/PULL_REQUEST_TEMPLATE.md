## What changes

## Why

## How it is verified
- [ ] a test that fails without this change
- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check .` passes
- [ ] no credentials, licensed data or workspace directories committed

## If this touches contracts or the harness
- [ ] the property it guarantees is stated in the test name
- [ ] `README.md`'s guarantees table is still accurate
