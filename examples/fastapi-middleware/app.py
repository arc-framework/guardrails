"""FastAPI app demonstrating the guard pipeline as route-level middleware."""

import asyncio

from arc_guard.pipeline import GuardPipeline
from arc_guard_core.types import GuardInput
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="arc-guard-example-fastapi-middleware")
pipeline = GuardPipeline()


@app.post("/with-guard")
async def with_guard(request: Request) -> JSONResponse:
    """Guarded route: pre-process the prompt before echoing it."""
    payload = await request.json()
    prompt = payload.get("prompt", "")
    result = await pipeline.pre_process(GuardInput(text=prompt))
    if result.action == "block" and result.refusal is not None:
        return JSONResponse(
            status_code=200,
            content={
                "guarded": True,
                "blocked": True,
                "refusal": {
                    "code": result.refusal.code,
                    "human_message": result.refusal.human_message,
                    "next_steps": list(result.refusal.next_steps),
                },
            },
        )
    return JSONResponse(
        status_code=200,
        content={"guarded": True, "blocked": False, "echo": result.text},
    )


@app.post("/without-guard")
async def without_guard(request: Request) -> JSONResponse:
    """Unguarded route: echo the prompt verbatim. Demonstrates the difference."""
    payload = await request.json()
    return JSONResponse(
        status_code=200,
        content={"guarded": False, "echo": payload.get("prompt", "")},
    )
