# Submission Readiness

## Current status

The package is a complete IEEE-style research draft with a deterministic
reference implementation, frozen protocols, raw results, analysis, tests, and
figures. All graph and local-MCP gates passed. The separately frozen hosted
extension passed six of seven gates; it missed only the absolute requirement
for five native attack attempts, observing three (20% of hosted attack trials).

The evidence supports a bounded claim: EpochCut maintains path closure in the
declared dynamic influence graph and prevented every observed injected effect
in both the local-model and hosted-model real-MCP deployments. The claim still assumes complete
instrumentation, trusted monitors, and serialised admission.

## Required before portal submission

1. Replace `Anonymous Authors` with the final author list, affiliations,
   ORCIDs, acknowledgements, and corresponding-author details as required by
   the selected review mode.
2. Obtain every co-author's approval and complete the authorship and conflict
   declarations.
3. Confirm that the work is not under review elsewhere and, if it extends a
   conference paper, document at least 30% new technical content and cite the
   earlier version.
4. Recheck the live special-issue page, select the special issue in ScholarOne,
   and conform the final source to the current IEEE template and policies.
5. For a broader production claim, add independent evaluation using a real
   multi-agent framework, remote MCP servers, additional hosted frontier
   models, and institutionally approved external effect services. The paper
   does not claim that this still-pending work has been completed.

## Reproducibility checks completed

- Nine unit tests pass.
- The 60,000-row raw CSV is preserved and SHA-256 bound to the analysis.
- Analysis regenerates all frozen claim gates and topology strata.
- The 126 real-LLM/MCP trials, transcripts, and persistent effect ledger are
  hash-bound; all MCP gates pass and recorded commits reconcile exactly.
- The 42 hosted-model/MCP trials are hash-bound; 42/42 completed without error,
  three native injected commits contrast with zero EpochCut commits, every
  observed guarded injection was blocked, and all 15 recorded commits
  reconcile exactly with the durable ledger. Six of seven hosted gates pass.
- The manuscript compiles without overfull boxes, undefined references, or
  LaTeX/package warnings.
- Every rendered PDF page was visually inspected for clipping, overlap,
  unreadable figures, and malformed tables.
