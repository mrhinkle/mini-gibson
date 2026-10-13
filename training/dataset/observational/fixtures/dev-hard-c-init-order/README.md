# DEV TASK: dev-hard-c-init-order
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #442).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: build_config(user) starts from defaults theme="light" and plugins=["core"].
- user is None or {} → those defaults, and no other keys
- a user theme replaces the default theme
- a user plugins list replaces the default list (it does not append)
- any other user key is kept

Examples:
- build_config(None) → {"theme": "light", "plugins": ["core"]}
- build_config({"theme": "dark"}) → theme dark, plugins ["core"]
- build_config({"plugins": ["extra"]}) → plugins ["extra"]
- build_config({"theme": "dark", "banner": True}) → theme dark and banner True

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
