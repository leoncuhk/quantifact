# Interactive run explorer

[`index.html`](index.html) is a self-contained view of a real Quantifact run:
its four bounded subsystems, end-to-end investment research workflow, critical
thinking contract, compiled plan, point-in-time comparison, contract evidence,
and reproducible benchmarks. The architecture SVG is inlined from the same
source used by the repository README, so arrow semantics cannot drift. The page
has no runtime dependencies and can be served directly by GitHub Pages.

The explorer shows implementation status explicitly. It is a synthetic,
reproducible architecture demonstration—not evidence of expert accuracy,
production isolation or investment performance. The repository maturity matrix
is the authoritative statement of remaining gates.

```bash
uv run python tools/export_site_data.py site/data.json   # run the system, export artefacts
uv run python tools/build_site.py                        # build site/index.html
```

It contains no credentials, no vendor data, no local paths and no endpoint
identity. The data is synthetic throughout. Generated output is committed so a
visitor can inspect it without installing the package; CI rebuilds it and fails
if the checked-in page has drifted.
