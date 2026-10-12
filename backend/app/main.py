"""
ContextLens API.

Run from the repository root:
    uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import importlib
import logging
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import chat, documents, health, research
from .api.errors import error_body, install_error_handlers
from .config import Settings, load_settings
from .container import Container, build_container

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("contextlens")
for _noisy in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def _preimport_ml_libraries() -> None:
    """transformers resolves attributes lazily and that is not thread-safe; import once before worker threads start."""
    for module in ("sentence_transformers", "mlx_lm"):
        try:
            importlib.import_module(module)
        except Exception:  # availability is reported later through /api/ready
            pass


def create_app(settings: Optional[Settings] = None, container: Optional[Container] = None) -> FastAPI:
    settings = settings or (container.settings if container else load_settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if container is None:
            _preimport_ml_libraries()
        c = container or build_container(settings)
        app.state.container = c
        interrupted = c.store.mark_interrupted()
        if interrupted:
            logger.warning("Marked %d interrupted document(s) as failed", interrupted)
        warm = getattr(c.embedder, "warm_up", None)
        if warm:
            threading.Thread(target=warm, name="embedding-warmup", daemon=True).start()
        if settings.llm_preload:
            c.llm.start_loading()
        yield
        c.close()

    app = FastAPI(title="ContextLens API", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.frontend_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    install_error_handlers(app)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request"
        message = str(first.get("msg", "Invalid request")).removeprefix("Value error, ")
        return JSONResponse(status_code=422, content=error_body("invalid_request", f"{field}: {message}"))

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(research.router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    s = load_settings()
    uvicorn.run("backend.app.main:app", host=s.backend_host, port=s.backend_port)
