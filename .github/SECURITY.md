# Security

## Reporting

Report vulnerabilities through GitHub's private security advisories on this
repository. Please do not open a public issue for anything exploitable.

## What quantifact executes

quantifact runs generated Python. It reduces the blast radius rather than
eliminating it:

- static analysis rejects imports, file and network IO, the clock, randomness
  and in-place mutation before anything runs;
- execution uses a restricted global namespace with a whitelist of builtins;
- loaders are bound to the plan's knowledge date and take no arguments.

This is **not a sandbox**. A determined escape from a restricted namespace is
possible in CPython. If you point quantifact at an untrusted model or untrusted
plans, run it in a container or a VM with no credentials and no network, and
treat the workspace directory as untrusted output.

## Credentials

The core ships no credentials and no data. Adapters read theirs from the
environment. Never commit an API key, a database path containing licensed data,
or a workspace directory; `.gitignore` covers the defaults and CI scans commits.
