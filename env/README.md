# Environment

Use Brev as disposable compute and Hugging Face as the artifact registry.

Reproducible runs must pin model, dataset, adapter, vLLM/training stack, Git SHA, and benchmark hash. Secrets are runtime-injected and never committed.

A future `doctor` command must fail closed when required pins or capabilities are missing.
