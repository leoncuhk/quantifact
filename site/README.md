# The interactive walkthrough

`blueprint.html` is a single self-contained page: thirteen passes, a real
compiled plan with its generated code, the point-in-time defence, the caching
benchmarks and the language-model grading runs — all rendered from data exported
by an actual run, so the page cannot drift from the code.

Published: https://claude.ai/code/artifact/3e2419d3-23b3-4975-b946-445cf23aee8f

## Rebuilding it

```bash
uv run python tools/export_site_data.py site/data.json   # runs the system, exports artefacts
uv run python tools/build_site.py                        # inlines the data into one file
```

`export_site_data.py` runs the whole pipeline three times (cold, warm, after a
teach loop), plus a second knowledge date for the point-in-time comparison, then
writes `site/data.json`. `build_site.py` merges the benchmark JSONs from
`benchmarks/` and inlines everything, so the page has no network dependencies.

## What it deliberately does not contain

No credentials, no vendor data, no client data, no local paths, and no endpoint
identity — only the model name, which is what makes a grading result meaningful.
The data is synthetic throughout.
