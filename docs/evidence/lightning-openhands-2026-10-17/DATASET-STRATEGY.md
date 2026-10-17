# Next training-data strategy

The important unit is not a raw task or pull request. It is a **successful, executable, uncontaminated trajectory rendered in the exact tool schema the model must use**.

## Recommended mix

1. Start with a stratified **2,000–5,000 successful** subset of [SWE-rebench OpenHands trajectories](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories). Balance repository, language, difficulty, trajectory length, and tool mix. Its card currently exposes 67,074 OpenHands trajectories; the companion [SWE-rebench V2](https://huggingface.co/datasets/nebius/SWE-rebench-V2) provides roughly 32,000 executable real-PR tasks across 20 languages.
2. Add **1,000–3,000** [Scale-SWE-Distilled](https://huggingface.co/datasets/AweAI-Team/Scale-SWE-Distilled) trajectories after converting and validating every tool call against the Mini-Gibson contract. Its current card exposes 71,498 OpenHands-style rows.
3. Use [SWE-smith Python](https://huggingface.co/datasets/SWE-bench/SWE-smith-py) as a **10–20% synthetic auxiliary curriculum**, not as the primary source. The approximately 50,000 rows are executable synthetic mutations, not 50,000 real merge requests or agent trajectories. Begin with 512 raw tasks, generate OpenHands rollouts, retain only successful and policy-clean traces, then expand to 2,000 and 5,000 only if the learning curve is positive.
4. Consider [SWE-bench-extra](https://huggingface.co/datasets/nebius/SWE-bench-extra) plus its [SWE-agent trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) for additional real-repository diversity after converting the action schema.
5. Defer [CommitPackFT](https://huggingface.co/datasets/bigcode/commitpackft) in the next comparison. Its large single-file commit corpus is useful as an edit prior but does not teach repository exploration, testing, or tool recovery.

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

Tool reliability is the immediate bottleneck. The next training run should test whether more successful, exact-schema trajectories reduce malformed responses without erasing the directional issue-resolution gain. Predeclare a maximum sample, the paired analysis, the malformed-response non-inferiority gate, and promotion criteria before inference begins.
