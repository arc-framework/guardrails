---
sidebar: false
aside: false
---

# Pipeline Swimlane

This board is the most compact visual summary of the runtime. It shows the shared observability surfaces, the 12-stage pipeline, and the main plugin families attached to each stage.

<CanvasFlow canvas-id="pipeline-swimlane" height="82vh" />

## What To Notice

- The main line stays left-to-right, but refusal branches peel off once routing resolves a blocking action.
- Observability is not bolted on at the end; it sits above the entire stage sequence.
- Inspectors, strategies, and reporters are attached to host stages rather than existing as a second pipeline.
