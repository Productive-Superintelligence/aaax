"""FastAPI server for AAAX strategies."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder

from .models import StrategyRunRequest, StrategyRunResponse
from .strategy import Strategy


def create_strategy_app(strategy: Strategy) -> FastAPI:
    """Expose a strategy as a FastAPI application."""

    app = FastAPI(
        title=strategy.name,
        description=strategy.description,
        version="0.2.0a0",
    )
    app.state.aaax_strategy = strategy

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "strategy": strategy.name}

    @app.get("/strategy")
    async def strategy_info() -> dict[str, Any]:
        return jsonable_encoder(strategy.info())

    @app.get("/resources")
    async def resources() -> list[dict[str, Any]]:
        return jsonable_encoder(strategy.resources)

    @app.post("/run", response_model=StrategyRunResponse)
    async def run(request: StrategyRunRequest) -> StrategyRunResponse:
        output = await strategy.arun(request.input, context=request.context)
        return StrategyRunResponse(
            output=jsonable_encoder(output),
            strategy=strategy.name,
        )

    @app.post("/resources/{name}/invoke", response_model=StrategyRunResponse)
    async def invoke_resource(
        name: str,
        request: StrategyRunRequest,
    ) -> StrategyRunResponse:
        try:
            output = await strategy.invoke_resource(
                name,
                request.input,
                context=request.context,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return StrategyRunResponse(
            output=jsonable_encoder(output),
            strategy=strategy.name,
            metadata={"resource": name},
        )

    return app
