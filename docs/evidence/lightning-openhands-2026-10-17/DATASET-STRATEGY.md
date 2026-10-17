# Next training-data strategy

The important unit is not a raw task or pull request. It is a **successful, executable, uncontaminated trajectory rendered in the exact tool schema the model must use**.

## Recommended mix

1. Start with a stratified **2,000–5,000 successful** subset of [SWE-rebench OpenHands trajectories](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories). Balance repository, language, difficulty, trajectory length, and tool mix. Its card currently exposes 67,074 OpenHands trajectories; the companion [SWE-rebench V2](https://huggingface.co/datasets/nebius/SWE-rebench-V2) provides roughly 32,000 executable real-PR tasks across 20 languages.
2. Add **1,000–3,000** [Scale-SWE-Distilled](https://huggingface.co/datasets/AweAI-Team/Scale-SWE-Distilled) trajectories after converting and validating every tool call against the Mini-Gibson contract. Its current card exposes 71,498 OpenHands-style rows.
3. Use [SWE-smith Python](https://huggingface.co/datasets/SWE-bench/SWE-smith-py) as a **10–20% synthetic auxiliary curriculum**, not as the primary source. The approximately 50,000 rows are executable synthetic mutations, not 50,000 real merge requests or agent trajectories. Begin with 512 raw tasks, generate OpenHands rollouts, retain only successful and policy-clean traces, then expand to 2,000 and 5,000 only if the learning curve is positive.
4. Consider [SWE-bench-extra](https://huggingface.co/datasets/nebius/SWE-bench-extra) plus its [SWE-agent trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) for additional real-repository diversity after converting the action schema.
5. Defer [CommitPackFT](https://huggingface.co/datasets/bigcode/commitpackft) in the next comparison. Its large single-file commit corpus is useful as an edit prior but does not teach repository exploration, testing, or tool recovery.

## Ray/Devstral-informed protocol changes

Ray Myers pointed us to the closest published analogue: [Devstral](https://arxiv.org/html/2509.25193v1), a 24B coding model trained from OpenHands CodeAct trajectories. Its procedure suggests four concrete changes for the next Mini-Gibson run:

1. Use a two-stage curriculum: first train on a broad set of executable, heuristically filtered successful rollouts; then finish on a smaller strict-quality tranche with clean verification, valid tools, minimal edits, no test changes, and useful recovery behavior.
2. Render matched examples in both the evaluator's XML tool syntax and native function-calling syntax. Split those renderings by underlying task so format variants of one task cannot cross train/development boundaries.
3. Keep deterministic pass@1 as the primary comparison. Report up to three attempts as a separate robustness measure, never as a replacement score or a way to retry until success.
4. Run a preregistered turn-budget ablation on new development tasks. Devstral found a large gain moving from 30 to 50 iterations and no further gain at 100; Mini-Gibson should test whether its current 10-turn limit is measuring coding ability or premature termination without rewriting the frozen 48-task result.

The [OpenHands Index analysis](https://www.openhands.dev/blog/analyzing-and-improving-openhands-index) also argues for behavior-level exploit audits, not just aggregate pass rates. New fixtures should use shallow or history-free clones, remain networkless, retain test-tamper and changed-file checks, and cluster traces for shortcut behavior. Evaluation should add secondary slices for testing and information-gathering behavior while preserving issue resolution as the primary endpoint.

## Non-negotiable contamination controls

Freeze one exclusion registry before sampling. It should contain:

- every current OpenHands train/development instance;
- all 48 issues in this evidence package;
- every final holdout and SWE-bench evaluation ID;
- repository/PR/base-commit keys;
- normalized patch and test hashes;
- issue-text similarity clusters;
- changed-file and AST-edit fingerprints;
- forks, backports, and trajectories derived from the same underlying task.

Split by repository and container image—not by row. Record the funnel for every source:

`source rows → executable tasks → successful trajectories → schema-valid traces → deduplicated/context-fit examples`

That funnel should be the primary data-quality graphic. Large source-row counts are otherwise easy to mistake for usable training signal.

## Next hypothesis

Tool reliability is the immediate bottleneck, but the 1024-token diagnostic showed that output length is only part of it. The next training run should test whether concise, successful, exact-schema trajectories reduce truncation, repeated execution errors, and boundary violations without erasing the directional issue-resolution gain. Predeclare a maximum sample, paired analysis, malformed-response and policy non-inferiority gates, and promotion criteria before inference begins.
