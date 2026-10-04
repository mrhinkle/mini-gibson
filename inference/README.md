# Inference

Reference path:

Hermes/conformant agent → OpenAI-compatible vLLM → pinned Nemotron base or promoted Mini Gibson adapter.

Required smoke sequence:
1. model server healthy;
2. /v1/models returns declared model;
3. deterministic minimal completion;
4. structured tool call;
5. agent connection;
6. GibsonEnv read-only tool action.
