---
sidebar: false
aside: false
---

# Request Decision Tree

This board compresses the common request outcomes into a single diagram. It is useful when you need to explain how the same classify stage can lead to `pass`, `redact`, or `block`.

<CanvasFlow canvas-id="request-flow-tree" height="74vh" />

## Reading Tips

- Start at the shared entry point and the classify node.
- Follow the branch that matches the finding set and risk band.
- Compare how the backend is still called for sanitized traffic but skipped for blocked traffic.
