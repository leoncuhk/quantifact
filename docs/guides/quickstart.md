# Quickstart

```bash
uv add git+https://github.com/leoncuhk/quantifact    # PyPI release pending
qf ask                     # the demo question, synthetic data, no key
qf ask                     # again — every task from the value cache
```

## What just happened

```
qf clarify        the four questions a planner asks before committing
qf plan           the compiled plan: layers, tasks, series bindings
qf ask            the whole pipeline, ending in .qf/report.html
qf catalog cpi    the catalog cards an agent reads when binding
qf search "US headline CPI year over year" --unit % --prior=-6,20
```

`qf search` is the one worth running twice — it prints why each candidate was
accepted or rejected, including the trap series that look right and are not.

## In Python

```python
from quantifact import Quantifact

qf = Quantifact(".qf")
art = qf.analyse(
    "How did markets respond to the oil supply shock?",
    answers={"as_of": "2026-06-14", "window_days": 20},
    out="report.html",
)

art.plan.as_of  # the knowledge date everything was bound to
art.result.trace("market_prices")  # cache key, rows, timing
art.verdicts  # every contract verdict, layer by layer
art.findings  # what self review noticed
art.written_series  # outputs written back into the store
```

## Choosing a knowledge date

`as_of` is the first clarifying question for a reason. Answering "today" for a
historical question is how look-ahead gets in. `qf ask --as-of 2026-06-14`
answers as of that morning: fewer episodes, less data, a different — and
defensible — answer.
