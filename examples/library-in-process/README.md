# Example: library-in-process

Use `arc-guard` as an in-process Python library — no HTTP server, no extras
beyond the default install.

## What this shows

The simplest possible integration: import `GuardPipeline`, build it once,
call `pre_process` on each user prompt before passing it to the LLM.

## Run

```bash
cd examples/library-in-process
pip install arc-guard
python main.py
```

Expected output:

```
benign  -> action=pass
jailbreak -> action=block, refusal=jailbreak_strong
```

## Trade-offs

- **Pros**: zero infrastructure cost; pipeline state lives in the same
  process as the application; lowest possible latency.
- **Cons**: each application process pays the model-load cost at startup;
  no central place to update guard configuration without redeploying.
