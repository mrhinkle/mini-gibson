# Off-host artifact archive receipt

On 17 October 2026, the completed Lightning run was copied from the non-stoppable Brev host to a non-repository artifact store before any instance-deletion decision.

## Bundle

- Archive: `mini-gibson-lightning-20261017.tgz`
- Size: 186,901,278 bytes
- Archive SHA-256: `75881702a163aa163cc3cfc7270c298bc1c4b0e84587b8fb2348d84c1a42c7ef`
- Sorted archive-path-list SHA-256: `cf5ea3b6de49934d523f8272a1a67c85b8f891bd4f17962d4c78c81d0d0112ed`

The bundle contains the training project and checkpoints, deployable inference adapter, final v8 evaluation outputs, and the 1024- and 1536-token diagnostics. The 62 GB base-model cache is excluded because it is reproducible from the pinned upstream model and revision.

## Adapter verification

The copied files reproduced the published hashes:

- Source adapter weights: `7acf4381661099918c3d41c8196f919dbebd6e496831e1af5c59de6bf857a612`
- Source adapter config: `eab35041a6f748319ff9450f8305e00a6789f7b005185bfd0d7a1ee605faf819`
- Inference adapter weights: `a7c6f56ea24527816a0a2c4aa652b7e28e4766ba902deaebb9186727d9bda23c`
- Inference adapter config: `1f2871fa1b90e1d546e5fb319ad39db4451514415535432d1764847e7513d410`

The inference adapter was then restored into a new directory and loaded in a fresh networkless NVIDIA NeMo AutoModel container using the pinned base-model cache. The smoke loaded all 188 tensors and 6,749,696 adapter parameters, reported `loaded_state_verified=true`, generated `READY`, and exited successfully.

This receipt records integrity and recoverability. The archive and model weights are deliberately not committed to Git.
