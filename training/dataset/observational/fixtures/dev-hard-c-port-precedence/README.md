# DEV TASK: dev-hard-c-port-precedence
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #442).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: resolve_port(cli_port, environ, file_port) picks one integer port.
Precedence, highest first:
1. cli_port when it is not None
2. environ["PORT"] when the key is present and the value is a non-empty string
3. file_port when it is not None
4. 8080

An empty PORT string is not a value. Treat it like a missing key. Do not turn it into 0.

Examples:
- (None, {}, None) → 8080
- (None, {}, 9000) → 9000
- (None, {"PORT": "7000"}, 9000) → 7000
- (None, {"PORT": ""}, 9000) → 9000
- (None, {"PORT": ""}, None) → 8080
- (3000, {"PORT": "7000"}, 9000) → 3000

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
