---
sidebar: false
aside: false
---

# Canvas Gallery

The repository already carries rich execution diagrams as `.canvas` files. This site reuses those source documents directly and renders them as interactive Vue Flow boards.

## Available Views

| Canvas                                               | Focus                                                  |
| ---------------------------------------------------- | ------------------------------------------------------ |
| [Pipeline Swimlane](/canvases/pipeline-swimlane)     | The shared 12-stage pipeline and its plugin lanes      |
| [Request Decision Tree](/canvases/request-flow-tree) | Pass, redact, and block outcomes in one branch diagram |
| [Detailed Request Flow](/canvases/request-flow)      | Full entry-to-response request walkthroughs            |
| [Benign Request DAG](/canvases/request-dag-benign)   | Event shape for a clean request                        |
| [PII Redaction DAG](/canvases/request-dag-pii)       | Event shape for a redaction path                       |
| [Blocked Request DAG](/canvases/request-dag-block)   | Event shape for a refusal-first request                |

## How To Use These Views

- Pan to inspect large flows without leaving the page.
- Use zoom controls or fit-view to reset large diagrams.
- Click a node to inspect its full label in the details panel.
- Treat these pages as live companions to the written guide and reference sections.
