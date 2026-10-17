# SWE-rebench V2 upstream schema smoke

Date: 2026-10-17

This is a parser/selection smoke, not a frozen cohort, qualification run, model
evaluation, or final-holdout result.

- `git ls-remote` resolved `nebius/SWE-rebench-V2` `HEAD` and `main` to
  `10483de0f50fe5da545942705a76c6150171af7f`.
- The Hugging Face dataset server returned the first 100 `train` rows while that
  revision was current.
- The live feature list matched the selector's required source shape, including
  task/repository identity, base commit, image name, language, license, patches,
  fail-to-pass/pass-to-pass lists, install configuration, test command, log
  parser, and quality metadata.
- The fail-closed prefilter accepted 53 of those 100 rows.
- The deterministic pilot selector filled all 24 candidate slots across 11
  languages and 24 repositories.
- Rejections in the 100-row smoke were: high-risk task surface 12, incomplete
  intent 27, quality confidence below 0.9 on 25, missing license 3, quality code
  other than A on 28, detected quality issue 28, and test-alignment issue 26.

The selector reconstructs a missing source-PR URL only when the official
`instance_id` has a numeric PR suffix and `repo` is a valid `owner/name`. The
final qualification lane must corroborate the reconstructed PR identity before
freezing a lock.

The final 24-task pilot and 144-task development cohort must be selected from a
complete export pinned to the revision above, screened against the real
exclusion registry, resolved to immutable image digests, and qualified twice.
The first-100-row smoke must not be used as either cohort.
