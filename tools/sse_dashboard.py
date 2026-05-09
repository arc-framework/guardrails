"""Live terminal dashboard for the arc-guard-service /events SSE feed.

Renders an auto-updating, color-coded table of every lifecycle event as it
streams from the api. Each rid gets a stable color; each event_type a
severity color (bold red for jailbreak / refusal / inspector failure;
bold yellow for findings; bold cyan for sanitization; dim for plumbing).

Usage:
    python tools/sse_dashboard.py [URL]

Default URL: http://127.0.0.1:8766/events
Press Ctrl-C to stop.

In an interactive terminal: a Rich Live table updates in place, last 30
events visible, status bar shows event count + active rid count.

When stdout is a pipe / file: falls back to one-line-per-event format
that survives logging.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text


URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8766/events"
MAX_ROWS = 30
CONNECT_RETRY_SECONDS = 2.0
CONNECT_RETRY_ATTEMPTS = 30


_RID_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "red", "bright_cyan", "bright_magenta"]
_rid_to_color: dict[str, str] = {}


def color_for_rid(rid: str) -> str:
    if rid not in _rid_to_color:
        _rid_to_color[rid] = _RID_COLORS[len(_rid_to_color) % len(_RID_COLORS)]
    return _rid_to_color[rid]


_TYPE_STYLES: dict[str, str] = {
    "RequestStarted": "bold green",
    "RequestCompleted": "bold green",
    "PreProcessStarted": "green",
    "PreProcessCompleted": "green",
    "PostProcessStarted": "blue",
    "PostProcessCompleted": "blue",
    "StageRan": "white",
    "InspectorRan": "yellow",
    "FindingProduced": "bold yellow",
    "JailbreakDetected": "bold red",
    "DeceptionScored": "magenta",
    "FidelityScored": "magenta",
    "SanitizationApplied": "bold cyan",
    "PolicyResolved": "cyan",
    "StrategyExecuted": "cyan",
    "DecisionEmitted": "bold blue",
    "RefusalProduced": "bold red",
    "BackendCalled": "blue",
    "BackendResponded": "blue",
    "ResponseAssembled": "green",
    "ReportFlushed": "dim",
    "IntentCaptured": "dim",
    "PolicyRuleEvaluated": "dim cyan",
    "InspectorMatchExplain": "bold yellow",
    "PlaceholderMapBuilt": "cyan",
    "InspectorFailed": "bold red",
    "RehydrationVerified": "magenta",
}


def _short(value: str | None, n: int = 8) -> str:
    return (value or "")[:n] or "-"


def _score(ev: dict) -> str:
    value = ev.get("score_value")
    band = ev.get("band", "not_measured")
    if value is None:
        sentinel = ev.get("score_sentinel") or band
        return f"band={band} ({sentinel})"
    return f"band={band} score={value:.2f}"


def _payload(label: str, text: str | None, limit: int = 80) -> str:
    if not text:
        return ""
    flat = text.replace("\n", "\\n").replace("\r", "")
    if len(flat) > limit:
        flat = flat[: limit - 1] + "…"
    return f' {label}="{flat}"'


def event_extras(ev: dict) -> str:
    et = ev["event_type"]
    if et == "RequestStarted":
        size = ev.get("input_size_bytes", 0)
        msgs = ev.get("msg_count")
        msg_part = f" msgs={msgs}" if msgs is not None else ""
        return (
            f"{ev.get('route')} model={ev.get('model')}{msg_part} {size}B"
            f"{_payload('input', ev.get('raw_input'))}"
        )
    if et == "RequestCompleted":
        pre = ev.get("pre_action", "pass")
        post = ev.get("post_action")
        post_part = f"/{post}" if post else ""
        return f"blocked={ev.get('blocked')} pre={pre}{post_part} {ev.get('total_duration_ms', 0):.1f}ms total"
    if et == "PreProcessStarted" or et == "PostProcessStarted":
        return f"corr={_short(ev.get('correlation_id'))} dec={_short(ev.get('decision_id'))}"
    if et == "PreProcessCompleted" or et == "PostProcessCompleted":
        return f"action={ev.get('action')} blocked={ev.get('blocked')} {ev.get('total_duration_ms', 0):.1f}ms"
    if et == "StageRan":
        status = ev.get("status", "ok")
        status_part = "" if status == "ok" else f" [{status}]"
        return f"stage={ev.get('stage')} {ev.get('duration_ms', 0):.1f}ms{status_part}"
    if et == "IntentCaptured":
        return f"encoder={ev.get('encoder_id')} {ev.get('intent_size_bytes', 0)}B"
    if et == "InspectorRan":
        return f"{ev.get('name')} findings={ev.get('findings_count')} {ev.get('duration_ms', 0):.1f}ms"
    if et == "FindingProduced":
        return (
            f"{ev.get('entity_type')} risk={ev.get('risk_level')} "
            f"score={ev.get('score', 0):.2f} span={ev.get('span')} by={ev.get('inspector')}"
        )
    if et == "JailbreakDetected":
        conf = ev.get("confidence", 0)
        return f"{ev.get('category')} conf={conf:.2f} det={ev.get('detector_id')}"
    if et == "DeceptionScored":
        prior = ev.get("prior_score")
        delta = ev.get("drift_delta")
        extras = []
        if prior is not None:
            extras.append(f"prior={prior:.2f}")
        if delta is not None:
            extras.append(f"delta={delta:+.2f}")
        tail = (" " + " ".join(extras)) if extras else ""
        return f"{_score(ev)} turns={ev.get('turn_count', 1)}{tail}"
    if et == "FidelityScored":
        return _score(ev)
    if et == "SanitizationApplied":
        return (
            f"{ev.get('entity_type')} -> {ev.get('placeholder')} "
            f"span={ev.get('span')} finding={_short(ev.get('finding_id'))}"
            f"{_payload('after', ev.get('text_after'))}"
        )
    if et == "PolicyResolved":
        return (
            f"action={ev.get('resolved_action')} risk={ev.get('max_risk')} "
            f"router={ev.get('router')}"
        )
    if et == "StrategyExecuted":
        return (
            f"{ev.get('strategy')} after={ev.get('text_after_size', 0)}B "
            f"finding={_short(ev.get('finding_id'))}"
        )
    if et == "DecisionEmitted":
        bypass = ev.get("bypass_reason")
        bypass_part = f" bypass={bypass}" if bypass else ""
        return f"action={ev.get('action')} risk={ev.get('max_risk')} id={_short(ev.get('decision_id'))}{bypass_part}"
    if et == "RefusalProduced":
        return f"code={ev.get('refusal_code')} chars={ev.get('human_message_chars', 0)} dec={_short(ev.get('decision_id'))}"
    if et == "BackendCalled":
        url = ev.get("url") or ""
        url_part = f" {url}" if url else ""
        return f"backend={ev.get('backend')} msgs={ev.get('payload_msg_count', 0)}{url_part}"
    if et == "BackendResponded":
        finish = ev.get("response_finish_reason")
        finish_part = f" finish={finish}" if finish else ""
        return (
            f"http={ev.get('http_status')} chars={ev.get('response_msg_chars')} "
            f"{ev.get('duration_ms', 0):.1f}ms{finish_part}"
            f"{_payload('reply', ev.get('response_text'))}"
        )
    if et == "PayloadRewritten":
        return (
            f"msg[{ev.get('message_index', 0)}].{ev.get('field', 'content')} "
            f"{ev.get('before_size', 0)}B -> {ev.get('after_size', 0)}B"
        )
    if et == "ResponseAssembled":
        return (
            f"id={_short(ev.get('response_id'))} finish={ev.get('finish_reason')} "
            f"blocked={ev.get('arc_guard_blocked')}"
        )
    if et == "ReportFlushed":
        reporters = ev.get("reporters") or []
        names = ",".join(reporters) if reporters else "-"
        failures = ev.get("failure_count", 0)
        fail_part = f" failures={failures}" if failures else ""
        return f"reporters=[{names}] fanout={ev.get('fanout_count', 0)}{fail_part}"
    if et == "PolicyRuleEvaluated":
        contrib = "*" if ev.get("contributed_to_action") else ""
        return f"rule={ev.get('rule_id')} {ev.get('outcome')}{contrib}"
    if et == "InspectorFailed":
        return f"{ev.get('inspector_name')} exc={ev.get('exception_class')} tb={_short(ev.get('traceback_id'))}"
    if et == "PlaceholderMapBuilt":
        types = ev.get("entity_types") or []
        types_part = f" types=[{','.join(types)}]" if types else ""
        mapping = ev.get("map") or {}
        if mapping:
            preview = ", ".join(f"{k}->{v}" for k, v in list(mapping.items())[:3])
            if len(mapping) > 3:
                preview += f", +{len(mapping) - 3} more"
            map_part = f' map={{{preview}}}'
        else:
            map_part = ""
        return f"count={ev.get('placeholder_count', 0)}{types_part}{map_part}"
    if et == "RehydrationVerified":
        reason = ev.get("rejection_reason")
        reason_part = f" reason={reason}" if reason else ""
        return f"verifier={ev.get('verifier_id')} {ev.get('outcome')}{reason_part}"
    if et == "InspectorMatchExplain":
        explanation = ev.get("explanation")
        exp_part = f" — {explanation}" if explanation else ""
        return f"{ev.get('inspector')} pattern={ev.get('pattern_id')} span={ev.get('matched_span')}{exp_part}"
    return ""


def build_table(rows: deque) -> Table:
    title = (
        f"[bold]arc-guard-service /events[/bold]  ({URL})  "
        f"·  {len(rows)} events  ·  rids: {len(_rid_to_color)}"
    )
    table = Table(
        title=title,
        title_style="bold white on dark_blue",
        show_lines=False,
        expand=True,
    )
    table.add_column("ts", style="dim", width=12)
    table.add_column("rid", width=22, no_wrap=True)
    table.add_column("seq", justify="right", width=4)
    table.add_column("event_type", width=22)
    table.add_column("parent", width=10, style="dim")
    table.add_column("details", overflow="ellipsis")

    for ev in rows:
        ts = datetime.fromisoformat(ev["ts"]).strftime("%H:%M:%S.%f")[:-3]
        rid = ev["rid"]
        rid_text = Text(rid, style=color_for_rid(rid))
        parent = (ev.get("parent_id") or "")[:8] or "-"
        et_style = _TYPE_STYLES.get(ev["event_type"], "white")
        et_text = Text(ev["event_type"], style=et_style)
        table.add_row(ts, rid_text, str(ev["seq"]), et_text, parent, event_extras(ev))
    return table


def _open_stream(console: Console):
    req = urllib.request.Request(URL, headers={"Accept": "text/event-stream"})
    last_err: Exception | None = None
    for attempt in range(CONNECT_RETRY_ATTEMPTS):
        try:
            return urllib.request.urlopen(req)
        except urllib.error.URLError as exc:
            last_err = exc
            console.print(
                f"[yellow]waiting for {URL} ({attempt + 1}/{CONNECT_RETRY_ATTEMPTS}): {exc.reason}[/yellow]",
            )
            time.sleep(CONNECT_RETRY_SECONDS)
    console.print(f"[bold red]could not reach {URL}: {last_err}[/bold red]")
    sys.exit(1)


def main() -> None:
    rows: deque = deque(maxlen=MAX_ROWS)
    console = Console()
    console.print(f"[bold]connecting to {URL}[/bold]  (Ctrl-C to stop)")

    stream = _open_stream(console)
    interactive = console.is_terminal

    if interactive:
        with Live(build_table(rows), console=console, refresh_per_second=10, screen=False) as live:
            for raw_line in stream:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[len("data: "):])
                except json.JSONDecodeError:
                    continue
                rows.append(ev)
                live.update(build_table(rows))
    else:
        for raw_line in stream:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
            if not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[len("data: "):])
            except json.JSONDecodeError:
                continue
            rows.append(ev)
            ts = datetime.fromisoformat(ev["ts"]).strftime("%H:%M:%S.%f")[:-3]
            parent = (ev.get("parent_id") or "")[:8] or "-"
            extras = event_extras(ev)
            line_text = Text()
            line_text.append(f"{ts}  ", style="dim")
            line_text.append(f"{ev['rid']:<22} ", style=color_for_rid(ev["rid"]))
            line_text.append(f"seq={ev['seq']:>2}  ")
            line_text.append(
                f"{ev['event_type']:<22}",
                style=_TYPE_STYLES.get(ev["event_type"], "white"),
            )
            line_text.append(f"  parent={parent}  {extras}", style="dim")
            console.print(line_text)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
