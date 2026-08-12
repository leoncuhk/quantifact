## What changes

## Why

## How it is verified
- [ ] a test that fails without this change
- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check src tests examples tools` passes
- [ ] `uv run qf audit` still reports evidence and gaps accurately
- [ ] no credentials, licensed data or workspace directories committed

## If this touches contracts or the harness
- [ ] the property it guarantees is stated in the test name
- [ ] `README.md`'s guarantees table is still accurate
