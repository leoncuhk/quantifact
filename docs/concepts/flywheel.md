# The flywheel

A system that gets better from use needs one thing more than a feedback button:
a way to tell whether the feedback changed anything.

## Reproduce, fix, prove nothing broke

```
complaint
   → an agent drafts a lesson naming an effect the planner understands
   → a benchmark is written that must FAIL against today's context
   → the lesson is applied; the benchmark must now PASS
   → the whole suite must still pass
   → only then are the lesson and benchmark written, for review
```

If the benchmark passes before the change, the lesson is refused: there was
nothing to learn. That single gate is what stops a context repository from
filling with prose that changed nothing.

## Lessons are verifiable, not vibes

```markdown
---
id: per-asset-class-panels
effect: per_asset_class_panels     # a hook the planner actually checks
when: multi_episode                # a feature that must hold
origin: teach
---
When comparing multiple historical episodes, break the analysis out by asset
class — FX, rates, equities and commodities transmit an oil shock through
fundamentally different channels, so a single pooled scatter hides more than it
reveals.
```

A lesson that maps to no effect cannot be verified, so `draft_lesson` refuses it
rather than storing text that will never fire.

## What it looks like in practice

```bash
qf teach "When comparing multiple historical episodes, break the analysis out by asset class"
```

```
lesson      per-asset-class-panels
benchmark   teach-per-asset-class-panels
reproduced  yes — benchmark failed before the change
fixed       yes
regressions 0
verdict     PR ready
```

The next run of a similar question emits an extra faceted chart task — and,
because of the cache, recomputes exactly that one task.

## Nothing merges itself

Acceptance writes files for review. The agent proposes; a human merges. In a
domain where a bad lesson quietly changes every future analysis, that boundary is
not bureaucracy.
