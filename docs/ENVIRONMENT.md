# Tested environment

Original GPU image: `/packages/apps/simg/vllm-cu129-nightly-0426.sif` on ASU Sol.

SHA-256 recorded during the original tests:

```text
31421e6384acb3813f1384c9c09e7209ed6454ae84293cde595ccb2e5146de79
```

Observed versions: vLLM `0.19.2rc1.dev212+g8cd174fa3.cu129`, PyTorch `2.11.0+cu129`, LMCache `0.4.4` (recorded build `0.4.4-g6fbec463e`), Transformers `5.6.2`.

Model: `Qwen/Qwen2.5-7B-Instruct`, revision `a09a35458c702b33eeacc393d103063234e8bc28`, BF16. Both model and tokenizer revision are explicitly pinned in the cleaned scripts. Native prefix caching is disabled. LMCache chunk size is 256 tokens.

Do not replace this stack with unconstrained latest packages and assume equivalent results. The quota and occupancy worker extensions depend on this image's internal backend layout. The image is supplied by the cluster, not this repository. A clean rebuild recipe is not yet established. Record new image hashes and versions if rebuilding.

GPU scale runs used an A100 80 GiB, 16 allocated CPU cores and 192 GiB allocated host RAM. Small tenant/quota diagnostics used an A30 24 GiB with 16 cores and 40 GiB host RAM. These are successful historical allocations, not promises of present availability.
