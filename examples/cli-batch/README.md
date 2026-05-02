# Example: cli-batch

Run `arc-guard` as a CLI step in a CI job or batch pipeline. Reads
JSON Lines `GuardInput` payloads from a file (or stdin), writes JSON
Lines `GuardResult` payloads to stdout (or a configurable output path).

## What this shows

The "batch / non-interactive" mode: no HTTP server, no long-running
process. One invocation per batch.

## Run

```bash
cd examples/cli-batch
pip install arc-guard-service

python batch.py inputs.jsonl > results.jsonl
```

Each line of `inputs.jsonl` is a JSON object with at minimum a `text` field;
each line of the output is the dataclass-asdict of the corresponding
`GuardResult`.

## CI wiring

```yaml
- name: Guard the batch
  run: |
    python examples/cli-batch/batch.py inputs.jsonl > results.jsonl
    jq -r 'select(.action == "block") | .refusal.code' results.jsonl
```

## Trade-offs

- **Pros**: simplest possible integration; no service to deploy or monitor;
  fits cleanly into any CI step.
- **Cons**: cold-start cost per invocation; not suitable for low-latency
  per-request use.
