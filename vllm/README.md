# vLLM Serving

Serve the pinned Nemotron base and, only if promoted, the Mini Gibson LoRA through an OpenAI-compatible endpoint.

Requirements:
- immutable base revision;
- pinned vLLM version;
- explicit served model name;
- validated GPU/tensor-parallel settings;
- completion and structured-tool smoke tests;
- no undeclared fallback model.

Reference served names: `nemotron-base` and conditional `mini-gibson`.

Exact serving flags remain UNPINNED until validated on the selected Brev profile.
