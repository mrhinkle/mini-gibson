# How Langfuse and Jev will help us improve Mini-Gibson

## The short, plain-English version

Langfuse and Jev answer different questions:

- **[Langfuse](https://github.com/langfuse/langfuse) shows the shape of the
  coding run.** It gives us a timeline of when the model responded, which tools
  ran, errors, retries, test runs, time, and token use. The planned first
  exporter would not send source code or message contents.
- **[Jev](https://typesafe.ai/) helps us sort operational problems.** After the real tests have produced
  an immutable result, the current Jev contract can classify a failure or flag
  it for human review using safe counts and status fields.
- **The local evaluator still decides whether a task passed.** Neither service
  can turn a failed task into a pass, change a score, choose a model for
  promotion, or authorize a retry.

This gives us a disciplined improvement loop: observe a completed run, identify
a repeated failure pattern, make one clearly stated change, and test that change
on fresh development tasks under a new written plan. We do not keep reusing the
same tasks or changing the experiment until the result looks good, and we do
not use the final holdout while developing.

## What this does and does not apply to

R3 is a **compatibility preflight**, not a model run. It checks whether each
frozen repository and patch package can be applied safely. It deliberately runs
no model, agent, parser, or tests.
Langfuse therefore has no agent trace to display, and Jev has no model
behavior to judge. The local hash-chained compatibility matrix is the right
evidence for this stage.

Langfuse and Jev become useful only after a future cohort has passed both the
complete compatibility preflight and deterministic qualification. Their first
use should be on development-only base, v1, and v2 model trials. The sealed
35-task final holdout remains unavailable until every preregistered development
gate passes.

## The operating boundary

Remote analysis must happen **only after the registered sequential experiment
has reached a terminal stop and its local results have been finalized**. An
intermediate look at N=144 or N=288 is not enough unless its preregistered rule
ends the experiment. If the experiment continues, no hosted analysis occurs
between cohorts A, B, and C.

1. Run every task required before the preregistered terminal stop in the
   locked-down evaluator.
2. Finish all deterministic tests and policy checks.
3. Write and hash every immutable local receipt and the final journal head.
4. Stop the scored controller and copy only the sealed receipts into a separate,
   read-only analysis workspace.
5. Create bounded, redacted analysis records from those receipts.
6. In a separate process with no evaluator, Docker, or Brev controls, send the
   records to Langfuse and, when requested, Jev. Post-run Jev analysis uses an
   explicit non-scored operator context (`run.scored: false`).
7. Record the Langfuse trace IDs and Jev decision receipts beside the local run.

A Langfuse or Jev outage cannot block, rerun, or invalidate a scored task. Their
credentials are not loaded until the experiment reaches a terminal stop and
the scored controller has stopped. They never enter the evaluator container or
controller environment and are never placed in model prompts, receipts, logs,
repository files, or Docker configuration. Hosted analysis is an optional
post-run side effect; local receipts remain the source of truth. No Langfuse or
Jev result may change any part of the experiment it analyzed.

## What Langfuse should show

Each completed development trial should become one Langfuse trace. Child
observations should represent model generations and tool calls in their
original order. The trace should make it easy to answer:

- Did the agent inspect the relevant files before editing?
- Did it repeat the same tool call or error without learning?
- How many turns, tokens, tool calls, and test executions did it use?
- Where did time accumulate: generation, tools, tests, or recovery?
- Did it stop too early, run out of budget, produce malformed output, or make an
  out-of-scope change?
- Which failure patterns are common across repositories, task types, and model
  arms?

The trace may contain only a small approved list of metadata fields, each with
a size limit. It should include immutable experiment and receipt identifiers,
source/model/adapter hashes, the frozen turn budget, safe event types, status,
timing and token counts, deterministic pass/fail, and policy flags. The first
version sends no prompt text, response text, source code, diff, issue text, tool
arguments, or tool output. It must also exclude credentials, environment dumps,
authentication headers, hidden tests, gold patches, private paths, and raw
Docker output.

Submitting a trace is not the same as proving it arrived. A successful export
requires a returned trace ID and then asking Langfuse for that trace by ID to
confirm it arrived. Failed exports are recorded as failed exports; they are not
silently presented as complete data.

## What Jev should review

The current `mini-gibson-jev/v1` contract is metadata-only. For this first
addition, Jev may receive only the safe fields already accepted by that
contract: terminal status, a bounded failure category, tool-error count,
infrastructure health, whether execution started, approved retry facts, and
declared tool identity and permission. It receives no source code, diff, prompt,
response, issue text, tool arguments, hidden answer, arm name, model name, or
promotion status.

Those fields let Jev classify operational anomalies and mark cases that need a
human review. They do not let Jev judge whether code is elegant, whether a patch
is semantically minimal, or whether a model's reasoning was good. Adding those
questions later would require a new versioned Jev contract and question set,
new privacy and redaction tests, a new data-contract hash, and independent
review before any hosted call.

Every analyzed arm uses the same pinned Jev model, questions, metadata format,
timeout, confidence threshold, and behavior when Jev fails. The record must
retain the policy hash, question-set version, resolved model, answers,
confidence, bounded error code, latency, and usage counts.

Jev's result is a diagnostic annotation, not a benchmark score. A failing
deterministic test cannot be overruled by a favorable Jev answer. Low
confidence, malformed output, missing credentials, service failure, or a stale
policy hash produces a visible fallback rather than an invented answer.

## The repeatable improvement loop

The R3 successor sequence is still at compatibility. It has reached none of the
planned base/v1/v2 comparisons or formal looks at N=144, N=288, or N=432.
If the full matrix contains incompatible tasks, they cannot be dropped to make
a smaller cohort. A general, outcome-blind evaluator repair and a new protocol
for the entire frozen cohort, or a genuinely fresh cohort, would be required
before another model trial. All 456 frozen tasks—the 24-task pilot plus cohorts A, B, and C—and the
35-task final holdout remain excluded from new training data. None may serve
as the fresh cohort for a change suggested by Langfuse or Jev. In any future
sequential model experiment, hosted analysis waits until the registered
terminal stop, and nothing learned from one development cohort may change the
arms, prompt, harness, budget, tools, or data for a later cohort.

After the sequence ends, a new model, prompt, harness, tool, budget, or
training-data hypothesis requires a new preregistered protocol and a fresh
development cohort from outside all experiment and training exclusions. If no
fresh cohort is available, the observations remain descriptive and cannot
support a new promotion claim.

For each permitted development cycle:

1. **Freeze the question.** State one proposed improvement before looking at
   the next comparison result—for example, reduce repeated file reads or make
   the agent run the narrow failing test before the full suite.
2. **Freeze the change.** Record the exact prompt, harness, training-data,
   adapter, tool, and budget hashes. Change only what the hypothesis requires.
3. **Run identical tasks and budgets within the cycle.** Compare the relevant
   model arms on the same fresh cohort using the same deterministic evaluator
   and preregistered stopping rules.
4. **Reach the registered stop first.** Hash every receipt, the complete
   results, and the final journal head before any remote analysis.
5. **Analyze behavior.** Use Langfuse aggregates and blinded Jev annotations to
   find repeated mechanisms, not isolated anecdotes.
6. **Classify the result.** Mark the hypothesis supported, unsupported, or
   inconclusive. Keep every failed and malformed trial in the totals.
7. **Choose the next single change.** Turn the strongest repeated failure mode
   into the next preregistered hypothesis on a new, non-overlapping cohort. Do
   not selectively rerun, replace tasks, reuse an examined cohort, alter budgets
   after outcomes, or chase statistical significance.
8. **Promote only through deterministic gates.** Langfuse and Jev can explain a
   result, but the frozen development statistics, safety checks, and local
   evaluator decide promotion and whether the final holdout may open.

## Minimum report for every cycle

Each cycle should add a public-safe evidence directory containing:

- the preregistered hypothesis and the single change being tested;
- experiment, dataset, cohort, source, model, adapter, prompt, tool, rubric,
  and policy hashes;
- the immutable local results and receipt-journal head;
- completion, failure, malformed-response, policy, turn, token, tool-call, and
  latency counts by arm;
- Langfuse export and confirmed-arrival counts plus safe trace references;
- Jev coverage, fallback counts, answer distributions, and agreement or
  disagreement with deterministic outcomes;
- a repository/task-type failure taxonomy with representative redacted traces;
- compute time and cost;
- the exact conclusion, limitations, and next preregistered hypothesis.

No report should claim that Langfuse itself improved the model or that Jev
proved correctness. Improvement means that a frozen model or harness change
performed better under the deterministic comparison, with the pre-set minimum
improvement, statistical, safety, and reproducibility gates satisfied.

## Implementation sequence

The next implementation addition should be a standalone post-run exporter,
not code inside the networkless evaluator:

1. Use the archived Lightning observability prototype only as design input. It
   is not safe to run as-is because it can include diffs, tool text, arm names,
   and model names and does not confirm that Langfuse received a trace.
2. Build a supported post-run module with a strict approved-field schema, size
   limits, stable IDs, and tests proving that hidden material and credentials
   cannot be exported.
3. Add offline fixtures and tests for Langfuse trace construction and Jev's
   typed anomaly answers and fallbacks without contacting either service.
4. Add a no-credentials local smoke that writes the exact records eligible for
   export.
5. After the registered experiment reaches a terminal stop, run one explicit
   post-run export and confirm that Langfuse returns the traces and that the Jev
   receipts are intact.
6. Freeze versions and hashes before using post-run analysis for the next
   base/v1/v2 development comparison.

This document authorizes no credential use or hosted request. Enabling either
service remains an explicit operational step after the exporter, redaction
tests, and experiment boundary have been independently reviewed.

Official references: [Langfuse documentation](https://langfuse.com/docs),
[TypeSafe Jev quickstart](https://docs.typesafe.ai/introduction/quickstart), and
[TypeSafe API reference](https://docs.typesafe.ai/api). The complete ecosystem
index is the repository-wide [project map](../../PROJECT-MAP.md).
