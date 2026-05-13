---
layout: home

hero:
  name: arc-guardrails
  text: Guardrails for production LLM systems
  tagline: A protocol-driven Python SDK and service surface for detecting, transforming, routing, and auditing risky AI traffic.
  actions:
    - theme: brand
      text: Read the guide
      link: /guide/
    - theme: alt
      text: Explore canvases
      link: /canvases/
    - theme: alt
      text: View reference
      link: /reference/

features:
  - title: Protocol-first extension
    details: Extend inspectors, strategies, lifecycle sinks, and policy surfaces without subclassing framework internals.
  - title: End-to-end request control
    details: Run validation, detection, sanitization, routing, refusal, verification, and reporting as one coherent pipeline.
  - title: Transport-neutral deployment
    details: Use the library in-process, through a service boundary, or alongside the operator dashboard and local stack.
---

<div class="arc-doc-badge">Three packages · one decision contract · one local developer surface</div>

arc-guardrails is an open source guardrails project for teams that need to keep sensitive or adversarial content under control before it reaches downstream language models. The repository packages the contract layer, the batteries-included runtime, and the service layer separately so operators can adopt only the surface they need.

## Start Here

<div class="arc-doc-grid">
  <a class="arc-doc-card arc-doc-card--link" href="/guide/">
    <h3>Guide</h3>
    <p>Understand the package split, the 12-stage execution model, and the local setup path that the Makefile already standardizes.</p>
    <span class="arc-doc-card__cta">Open section -></span>
  </a>
  <a class="arc-doc-card arc-doc-card--link" href="/reference/">
    <h3>Reference</h3>
    <p>Trace the pipeline, the API surface, observability hooks, and the detection coverage matrix from the existing knowledge base.</p>
    <span class="arc-doc-card__cta">Open section -></span>
  </a>
  <a class="arc-doc-card arc-doc-card--link" href="/canvases/">
    <h3>Canvases</h3>
    <p>Use interactive request and pipeline flow views derived from the repository’s existing canvas documents.</p>
    <span class="arc-doc-card__cta">Open section -></span>
  </a>
  <a class="arc-doc-card arc-doc-card--link" href="/guide/setup">
    <h3>Run Locally</h3>
    <p>Use the repository Makefile to install packages, boot the API, start Docker services, and exercise the stack on any machine.</p>
    <span class="arc-doc-card__cta">Open section -></span>
  </a>
</div>

## Reading Paths

- New to the project: start with [Guide](/guide/), then move to the architecture and pipeline reference pages.
- Evaluating integration fit: jump to [Reference](/reference/) for packages, API surface, and technology inventory.
- Explaining flows to operators or contributors: use [Canvases](/canvases/) for request lifecycles and branch behavior.
