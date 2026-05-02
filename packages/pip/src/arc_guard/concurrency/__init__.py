"""Concurrency primitives for the arc-guard pipeline.

Hosts the async-offload helper. The frozen-after-construction registry
helper lives in ``arc_guard_core._registry_lock`` so both core's
``EntityRegistry`` and pip's ``StrategyRegistry`` share one
implementation without crossing the layered-import boundary.
"""

from __future__ import annotations

from arc_guard.concurrency.offload import OFFLOAD_COUNTER, run_off_loop

__all__ = ["run_off_loop", "OFFLOAD_COUNTER"]
