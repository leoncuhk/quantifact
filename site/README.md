# The interactive walkthrough

`blueprint.html` is one self-contained page — passes, a real compiled plan with
its generated code, the point-in-time defence, the benchmarks — rendered from
data exported by an actual run, so it cannot drift from the code.

```bash
uv run python tools/export_site_data.py site/data.json   # run the system, export artefacts
uv run python tools/build_site.py                        # inline them into one file
```

It contains no credentials, no vendor data, no local paths and no endpoint
identity — only the model name, which is the part that makes a grading result
mean anything. The data is synthetic throughout.
