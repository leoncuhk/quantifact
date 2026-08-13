# ADR 0004: the evidence package is the product

## Status

Accepted.

## Decision

Every successful run produces a versioned `ResearchEvidencePackage`. Reports,
CLI summaries and future conversations are projections of it. The package
includes the compiled plan, generated code, source-vintage manifest, output
fingerprints, contracts, repairs, claim lineage and an integrity hash.

The admission state is named `admitted_for_expert_review`; it explicitly sets
`investment_approved=false`.

## Consequences

- A run's internal hashes can be verified offline with `qf verify`; publisher
  authenticity requires a trusted external signature or registry.
- Claims can be traversed to tasks, source series, code and value identity.
- Interfaces can evolve without changing the durable research object.
- Packages contain code and metadata and must be protected according to the
  connected data licence and the institution's research-confidentiality rules.
- A self-contained integrity hash detects inconsistency but is not a digital
  signature: an attacker able to replace the whole package can recompute it.
  Integrity proves neither publisher identity nor that an inference is true.
