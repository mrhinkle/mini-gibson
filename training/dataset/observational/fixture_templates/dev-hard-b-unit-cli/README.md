# DEV TASK: dev-hard-b-unit-cli
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #441).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: convert meters to a unit, and the CLI must pass that unit through.
- "m" returns the meters unchanged
- "km" divides by 1000
- "mi" divides by 1600
- any other unit raises ValueError
- cli_main([meters, unit]) returns the same number as convert

Examples:
- convert(2500, "km") == 2.5
- convert(1600, "mi") == 1
- cli_main(["1600", "mi"]) == 1
- cli_main(["1000", "km"]) == 1

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
