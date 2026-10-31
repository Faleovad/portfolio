import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import mutations, orders, scenarios, system, warehouse
from .container import Lab
from .domain.errors import LabError


def create_app(data_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Order Reliability Lab", version="0.1.0")
    app.state.lab = Lab(data_dir or Path(os.environ.get("LAB_DATA_DIR", ".data")))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(LabError)
    async def lab_error(_request: Request, error: LabError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status,
            content={"error": {"code": error.code, "message": error.message}},
        )

    for router in (
        scenarios.router,
        orders.router,
        warehouse.router,
        mutations.router,
        system.router,
    ):
        app.include_router(router)
    return app
