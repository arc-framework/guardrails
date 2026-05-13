---
sidebar: false
aside: false
---

# Detailed Request Flow

This is the highest-detail canvas in the set. It traces multiple request shapes through transport middleware, schema validation, pipeline stages, sinks, and final response assembly.

<CanvasFlow canvas-id="request-flow" height="86vh" />

## Suggested Uses

- Follow a request end-to-end while debugging integration behavior.
- Compare the service path for clean traffic, redaction paths, and hard blocks.
- Review where observability is emitted and where the backend is bypassed entirely.
