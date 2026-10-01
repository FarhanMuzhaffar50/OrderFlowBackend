import json
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.router import router as auth_router
from app.carts.router import router as cart_router
from app.common.redis import redis_client
from app.core.config import get_settings
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.orders.router import router as orders_router
from app.payments.router import router as webhook_router
from app.products.router import router as products_router

HTTP_REQUESTS = Counter(
    "orderflow_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
HTTP_LATENCY = Histogram(
    "orderflow_http_request_duration_seconds", "Request latency", ["method", "path"]
)
logger = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - started
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, path, response.status_code).inc()
        HTTP_LATENCY.labels(request.method, path).observe(duration)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    yield
    await redis_client.aclose()


app = FastAPI(title="OrderFlow", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
install_exception_handlers(app)
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(webhook_router)


@app.get("/health", tags=["operations"])
async def health():
    return {"status": "ok"}


@app.get("/ready", tags=["operations"])
async def ready():
    failures = []
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        failures.append("postgres")
    try:
        await redis_client.ping()
    except Exception:
        failures.append("redis")
    if failures:
        return Response(
            content=json.dumps({"status": "not_ready", "dependencies": failures}),
            status_code=503,
            media_type="application/json",
        )
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
