"""DarPilot FastAPI application entry point.

Initializes database, configures CORS, security headers, rate limiting,
and includes API routes.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.database import init_db
from backend.routes import router as routes_app, limiter


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="DarPilot",
        description="Secure-by-design AI real-estate assistant (synthetic data).",
        version="0.1.0",
    )

    # Rate limiting (slowapi) — keyed by client IP.
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
        )

    # CORS — strict: only known origins. Override via DARPILOT_CORS_ORIGINS
    # (comma-separated). Defaults to no origins (locked down).
    cors_raw = __import__("os").environ.get("DARPILOT_CORS_ORIGINS", "")
    allow_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Security headers on every response.
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers[
            "Content-Security-Policy"
        ] = "default-src 'self'; frame-ancestors 'none';"
        return response

    # Include API routes
    app.include_router(routes_app)

    @app.on_event("startup")
    async def startup():
        init_db()

    return app


app = create_app()
