"""A synthetic NeMo Gym smoke verifier for the malformed-tool-call failure mode.

This is deliberately not the Mini Gibson issue-resolution scorer. It checks only
whether a model emitted one well-formed apply_patch function call, and never
executes a patch, runs tests, or consults a sealed task.
"""

import json
from pathlib import Path
from typing import ClassVar

from nemo_gym.base_resources_server import (
    BaseResourcesServerConfig,
    BaseVerifyRequest,
    BaseVerifyResponse,
    ReverifyMode,
    SimpleResourcesServer,
)
from nemo_gym.verifier_fixture import VerifierFixture


class MiniGibsonToolCallConfig(BaseResourcesServerConfig):
    REVERIFY_MODE: ClassVar[ReverifyMode] = ReverifyMode.STATELESS


def valid_patch_call(output: object) -> bool:
    """Accept only the agreed tool name and a single JSON patch argument."""
    if getattr(output, "type", None) != "function_call" or getattr(output, "name", None) != "apply_patch":
        return False
    try:
        arguments = json.loads(getattr(output, "arguments", ""))
    except (TypeError, ValueError):
        return False
    if not isinstance(arguments, dict) or set(arguments) != {"patch"}:
        return False
    patch = arguments["patch"]
    return (
        isinstance(patch, str)
        and patch.startswith("*** Begin Patch\n")
        and patch.rstrip().endswith("*** End Patch")
    )


class MiniGibsonToolCallVerifier:
    async def verify(self, body: BaseVerifyRequest) -> BaseVerifyResponse:
        # Format-only signal. A real issue score requires GibsonEnv's immutable
        # networkless execution receipt, not a model-authored assertion.
        output = body.response.output
        reward = float(len(output) == 1 and valid_patch_call(output[0]))
        return BaseVerifyResponse(**body.model_dump(), reward=reward)


class MiniGibsonToolCallServer(MiniGibsonToolCallVerifier, SimpleResourcesServer):
    config: MiniGibsonToolCallConfig


VERIFIER_FIXTURE = VerifierFixture(
    server_factory=MiniGibsonToolCallVerifier,
    request_model=BaseVerifyRequest,
    cases_path=Path(__file__).parent / "tests" / "verifier_cases.jsonl",
)


if __name__ == "__main__":
    MiniGibsonToolCallServer.run_webserver()
