"""Dashboard data-plane HTTP routes.

Four read-only routes built on the dashboard SQLite tier created by
``arc_guard.observability.sqlite_lifecycle_sink``'s schema-v2 migration:

- ``GET /requests`` — paginated explorer table.
- ``GET /requests/{rid}`` — workspace manifest.
- ``GET /requests/{rid}/decision`` — recorded ``DecisionRecord``.
- ``GET /requests/{rid}/debug`` — cursor-paginated debug entries.

Each handler opens its own read-only SQLite connection against the
configured ``lifecycle_sqlite_path``. When the path is unset, the router
returns 503 with a stable error envelope; callers can probe the route
to detect "this deployment doesn't have the dashboard data plane wired
up" without a separate health check.
"""

from __future__ import annotations

import importlib
import logging
import re
import sqlite3
from datetime import datetime
from typing import Any

from arc_guard_core.schemas import (
    RequestDebugEntry,
    RequestDebugPage,
    RequestDecisionEnvelope,
    RequestPage,
    RequestPageFilters,
    RequestSummary,
    RequestWorkspaceManifest,
    WorkspaceResourceLinks,
    WorkspaceResourcesAvailability,
    decode_debug_cursor,
    encode_debug_cursor,
)

from arc_guard_service.settings import ServiceSettings

_LOG = logging.getLogger("arc_guard.dashboard.requests")

_RID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_VALID_STATUSES = {"live", "completed", "errored"}
_VALID_ACTIONS = {"pass", "block", "redact", "clarify", "refuse"}
_VALID_RISK_BANDS = {"low", "med", "high"}


def _open_read_conn(path: str) -> sqlite3.Connection:
    """Open a connection. We don't enforce read-only at the connection layer
    (sqlite3 makes that awkward) — the SQL we issue from these handlers is
    exclusively SELECT, so writes are impossible by construction. WAL mode
    lets us share the file with the writer sinks."""
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _row_to_summary(row: sqlite3.Row) -> RequestSummary:
    return RequestSummary(
        rid=row["rid"],
        started_at=datetime.fromisoformat(row["started_at"]),
        last_event_at=datetime.fromisoformat(row["last_event_at"]),
        status=row["status"],
        final_action=row["final_action"],
        max_risk=row["max_risk"],
        duration_ms=row["duration_ms"],
        refusal_code=row["refusal_code"],
        decision_id=row["decision_id"],
        live=bool(row["live"]),
        stage=row["stage"],
    )


def _build_filter_clause(
    *,
    since: datetime | None,
    until: datetime | None,
    statuses: list[str],
    actions: list[str],
    risk_bands: list[str],
    rid_prefix: str | None,
) -> tuple[str, list[Any]]:
    """Build a parameterized WHERE clause from validated filter args.

    Risk-band thresholds: low = max_risk < 0.5; med = 0.5..0.85; high >= 0.85.
    These match the existing PolicyResolved band labels used elsewhere in
    the pipeline; centralize when stabilized as a public contract.
    """
    where: list[str] = []
    params: list[Any] = []
    if since is not None:
        where.append("started_at >= ?")
        params.append(since.isoformat())
    if until is not None:
        where.append("started_at < ?")
        params.append(until.isoformat())
    if statuses:
        where.append("status IN (" + ",".join("?" for _ in statuses) + ")")
        params.extend(statuses)
    if actions:
        where.append("final_action IN (" + ",".join("?" for _ in actions) + ")")
        params.extend(actions)
    if risk_bands:
        band_clauses: list[str] = []
        for band in risk_bands:
            if band == "low":
                band_clauses.append("(max_risk IS NULL OR max_risk < 0.5)")
            elif band == "med":
                band_clauses.append("(max_risk >= 0.5 AND max_risk < 0.85)")
            elif band == "high":
                band_clauses.append("(max_risk >= 0.85)")
        if band_clauses:
            where.append("(" + " OR ".join(band_clauses) + ")")
    if rid_prefix is not None:
        # Case-sensitive prefix match via substr comparison. SQLite's LIKE is
        # case-insensitive by default and PRAGMA-level toggles affect the
        # whole connection — substr() is per-query and unambiguous.
        where.append("substr(rid, 1, ?) = ?")
        params.append(len(rid_prefix))
        params.append(rid_prefix)
    if not where:
        return "", []
    return "WHERE " + " AND ".join(where), params


def build_requests_router(*, settings: ServiceSettings) -> Any:
    """Construct a FastAPI router exposing ``GET /requests``."""
    fastapi = importlib.import_module("fastapi")
    APIRouter = fastapi.APIRouter  # noqa: N806
    HTTPException = fastapi.HTTPException  # noqa: N806
    Query = fastapi.Query  # noqa: N806
    JSONResponse = fastapi.responses.JSONResponse  # noqa: N806

    router = APIRouter()

    def _dashboard_unavailable() -> Any:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "store_unavailable",
                    "message": (
                        "lifecycle_sqlite_path not configured; dashboard data plane unavailable"
                    ),
                }
            },
            headers={"Retry-After": "30"},
        )

    @router.get(
        "/requests",
        summary="Paginated request-summary list for the dashboard explorer",
        tags=["dashboard"],
    )
    async def list_requests(
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1),
        since: datetime | None = Query(None),
        until: datetime | None = Query(None),
        status: list[str] | None = Query(None),
        action: list[str] | None = Query(None),
        risk_band: list[str] | None = Query(None),
        rid_prefix: str | None = Query(None),
    ) -> Any:
        if page_size > settings.dashboard_max_request_page_size:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "invalid_query",
                        "message": (
                            f"page_size must be 1..{settings.dashboard_max_request_page_size}"
                        ),
                    }
                },
            )
        statuses = list(status or [])
        for s in statuses:
            if s not in _VALID_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "invalid_query",
                            "message": f"unknown status {s!r}",
                        }
                    },
                )
        actions = list(action or [])
        for a in actions:
            if a not in _VALID_ACTIONS:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "invalid_query",
                            "message": f"unknown action {a!r}",
                        }
                    },
                )
        risk_bands = list(risk_band or [])
        for rb in risk_bands:
            if rb not in _VALID_RISK_BANDS:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "invalid_query",
                            "message": f"unknown risk_band {rb!r}",
                        }
                    },
                )

        if not settings.lifecycle_sqlite_path:
            return _dashboard_unavailable()

        try:
            conn = _open_read_conn(settings.lifecycle_sqlite_path)
        except sqlite3.Error as exc:
            _LOG.warning("dashboard sqlite open failed: %s", exc)
            return _dashboard_unavailable()

        try:
            where_sql, params = _build_filter_clause(
                since=since,
                until=until,
                statuses=statuses,
                actions=actions,
                risk_bands=risk_bands,
                rid_prefix=rid_prefix,
            )
            count_sql = "SELECT COUNT(*) FROM request_summaries " + (where_sql if where_sql else "")
            try:
                total = int(conn.execute(count_sql, params).fetchone()[0])
            except sqlite3.Error as exc:
                _LOG.warning("dashboard count query failed: %s", exc)
                return _dashboard_unavailable()

            offset = (page - 1) * page_size
            list_sql = (
                "SELECT * FROM request_summaries "
                + (where_sql + " " if where_sql else "")
                + "ORDER BY started_at DESC LIMIT ? OFFSET ?"
            )
            try:
                rows = conn.execute(list_sql, [*params, page_size, offset]).fetchall()
            except sqlite3.Error as exc:
                _LOG.warning("dashboard list query failed: %s", exc)
                return _dashboard_unavailable()
        finally:
            conn.close()

        items = tuple(_row_to_summary(r) for r in rows)
        page_resp = RequestPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_more=(offset + len(items)) < total,
            filters=RequestPageFilters(
                since=since,
                until=until,
                status=tuple(statuses),  # type: ignore[arg-type]
                action=tuple(actions),  # type: ignore[arg-type]
                risk_band=tuple(risk_bands),  # type: ignore[arg-type]
                rid_prefix=rid_prefix,
            ),
        )
        return JSONResponse(
            status_code=200,
            content=page_resp.model_dump(mode="json"),
        )

    def _validate_rid(rid: str) -> None:
        if not _RID_PATTERN.match(rid):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "rid_malformed",
                        "message": "rid must match [A-Za-z0-9._-]{1,64}",
                    }
                },
            )

    def _open_or_503() -> Any:
        if not settings.lifecycle_sqlite_path:
            return _dashboard_unavailable()
        try:
            return _open_read_conn(settings.lifecycle_sqlite_path)
        except sqlite3.Error as exc:
            _LOG.warning("dashboard sqlite open failed: %s", exc)
            return _dashboard_unavailable()

    @router.get(
        "/requests/{rid}",
        summary="Workspace manifest for one request",
        tags=["dashboard"],
    )
    async def get_request_detail(rid: str) -> Any:
        _validate_rid(rid)
        conn_or_resp = _open_or_503()
        if isinstance(conn_or_resp, sqlite3.Connection):
            conn = conn_or_resp
        else:
            return conn_or_resp
        try:
            try:
                row = conn.execute(
                    "SELECT * FROM request_summaries WHERE rid = ?", (rid,)
                ).fetchone()
            except sqlite3.Error as exc:
                _LOG.warning("dashboard summary query failed: %s", exc)
                return _dashboard_unavailable()
            if row is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "code": "rid_not_found",
                            "message": "rid not found in any configured store",
                        }
                    },
                )
            summary = _row_to_summary(row)
            decision_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM decision_records WHERE rid = ?",
                    (rid,),
                ).fetchone()[0]
            )
            debug_count = int(
                conn.execute("SELECT COUNT(*) FROM debug_entries WHERE rid = ?", (rid,)).fetchone()[
                    0
                ]
            )
        finally:
            conn.close()
        manifest = RequestWorkspaceManifest(
            summary=summary,
            resources=WorkspaceResourcesAvailability(
                lifecycle=True,
                decision=decision_count > 0,
                debug=debug_count > 0,
                live_stream=summary.live,
            ),
            links=WorkspaceResourceLinks(
                lifecycle=f"/lifecycle/{rid}",
                decision=f"/requests/{rid}/decision",
                debug=f"/requests/{rid}/debug",
                live_stream=f"/events?rid={rid}",
            ),
        )
        return JSONResponse(
            status_code=200,
            content=manifest.model_dump(mode="json"),
        )

    @router.get(
        "/requests/{rid}/decision",
        summary="DecisionRecord retrieval for one request",
        tags=["dashboard"],
    )
    async def get_request_decision(rid: str) -> Any:
        _validate_rid(rid)
        conn_or_resp = _open_or_503()
        if isinstance(conn_or_resp, sqlite3.Connection):
            conn = conn_or_resp
        else:
            return conn_or_resp
        try:
            try:
                row = conn.execute(
                    "SELECT * FROM decision_records WHERE rid = ?"
                    " ORDER BY recorded_at DESC LIMIT 1",
                    (rid,),
                ).fetchone()
            except sqlite3.Error as exc:
                _LOG.warning("dashboard decision query failed: %s", exc)
                return _dashboard_unavailable()
        finally:
            conn.close()
        if row is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "decision_not_captured",
                        "message": "no DecisionRecord recorded for this rid",
                    }
                },
            )
        import json as _json

        envelope = RequestDecisionEnvelope(
            rid=row["rid"],
            decision_id=row["decision_id"],
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            decision=_json.loads(row["payload_json"]),
            payload_size_bytes=row["payload_size_bytes"],
        )
        return JSONResponse(
            status_code=200,
            content=envelope.model_dump(mode="json"),
        )

    @router.get(
        "/requests/{rid}/debug",
        summary="Cursor-paginated debug entries for one request",
        tags=["dashboard"],
    )
    async def get_request_debug(
        rid: str,
        page_size: int = Query(100, ge=1),
        cursor: str | None = Query(None),
    ) -> Any:
        _validate_rid(rid)
        if page_size > settings.dashboard_max_debug_page_size:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "invalid_query",
                        "message": (
                            f"page_size must be 1..{settings.dashboard_max_debug_page_size}"
                        ),
                    }
                },
            )
        after_seq = 0
        if cursor is not None:
            try:
                after_seq = decode_debug_cursor(cursor, expected_rid=rid)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": (
                                "cursor_mismatch"
                                if "does not match" in str(exc)
                                else "cursor_invalid"
                            ),
                            "message": str(exc),
                        }
                    },
                ) from exc
        conn_or_resp = _open_or_503()
        if isinstance(conn_or_resp, sqlite3.Connection):
            conn = conn_or_resp
        else:
            return conn_or_resp
        try:
            # First, check the rid exists at all.
            try:
                summary_exists = (
                    conn.execute(
                        "SELECT 1 FROM request_summaries WHERE rid = ? LIMIT 1",
                        (rid,),
                    ).fetchone()
                    is not None
                )
                debug_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM debug_entries WHERE rid = ?",
                        (rid,),
                    ).fetchone()[0]
                )
                if not summary_exists and debug_count == 0:
                    return JSONResponse(
                        status_code=404,
                        content={
                            "error": {
                                "code": "rid_not_found",
                                "message": "rid not found in any configured store",
                            }
                        },
                    )
                if debug_count == 0:
                    return JSONResponse(
                        status_code=404,
                        content={
                            "error": {
                                "code": "debug_not_captured",
                                "message": "no debug entries recorded for this rid",
                            }
                        },
                    )
                rows = conn.execute(
                    "SELECT * FROM debug_entries"
                    " WHERE rid = ? AND seq > ?"
                    " ORDER BY seq ASC LIMIT ?",
                    (rid, after_seq, page_size),
                ).fetchall()
            except sqlite3.Error as exc:
                _LOG.warning("dashboard debug query failed: %s", exc)
                return _dashboard_unavailable()
        finally:
            conn.close()
        import json as _json

        items = tuple(
            RequestDebugEntry(
                rid=r["rid"],
                seq=r["seq"],
                ts=datetime.fromisoformat(r["ts"]),
                channel=r["channel"],
                severity=r["severity"],
                message=r["message"],
                metadata=_json.loads(r["metadata_json"]),
            )
            for r in rows
        )
        next_cursor = (
            encode_debug_cursor(rid=rid, seq=items[-1].seq) if len(items) == page_size else None
        )
        page = RequestDebugPage(
            rid=rid,
            items=items,
            next_cursor=next_cursor,
            page_size=page_size,
        )
        return JSONResponse(
            status_code=200,
            content=page.model_dump(mode="json"),
        )

    return router


__all__ = ["build_requests_router"]
