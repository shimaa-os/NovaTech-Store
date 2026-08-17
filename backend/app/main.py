from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import get_settings
from .db import engine
from .redis_client import get_redis
from .routers import admin, auth, cart, checkout, products, profile
from .services.csrf import create_csrf_token, enforce_csrf

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title="NovaTech Store", version="2.0.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.middleware("http")
    async def security_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            await enforce_csrf(request)
            response = await call_next(request)
        except HTTPException as exc:
            response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        add_security_headers(response, request)
        return response

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/ready")
    async def ready() -> dict:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        await get_redis().ping()
        return {"status": "ready"}

    @app.get("/api/auth/csrf")
    async def csrf(response: Response) -> dict:
        token = create_csrf_token(response)
        return {"status": "success", "csrfToken": token}

    app.include_router(auth.router)
    app.include_router(products.router)
    app.include_router(cart.router)
    app.include_router(checkout.router)
    app.include_router(profile.router)
    app.include_router(admin.router)

    images_dir = settings.frontend_dir / "images"
    if images_dir.exists():
        app.mount("/images", StaticFiles(directory=images_dir, html=False), name="images")

    @app.api_route("/", methods=["GET", "HEAD"])
    @app.api_route("/index.html", methods=["GET", "HEAD"])
    async def index() -> FileResponse:
        return FileResponse(_static_file("index.html"))

    @app.api_route("/styles.css", methods=["GET", "HEAD"])
    async def styles() -> FileResponse:
        return FileResponse(_static_file("styles.css"), media_type="text/css")

    @app.api_route("/app.js", methods=["GET", "HEAD"])
    async def script() -> FileResponse:
        return FileResponse(_static_file("app.js"), media_type="application/javascript")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"])
    async def not_found(path: str) -> JSONResponse:
        return JSONResponse({"detail": "Not found"}, status_code=404)

    return app


def _static_file(name: str) -> Path:
    path = (settings.frontend_dir / name).resolve()
    root = settings.frontend_dir.resolve()
    if root not in path.parents and path != root:
        raise HTTPException(status_code=404, detail="Not found")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return path


def add_security_headers(response: Response, request: Request) -> None:
    asset_sources = ["'self'", "data:"]
    if settings.asset_origin:
        asset_sources.append(settings.asset_origin)
    csp = (
        "default-src 'self'; "
        "base-uri 'none'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        f"img-src {' '.join(asset_sources)}; "
        "connect-src 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), microphone=(), payment=()"
    response.headers["X-Frame-Options"] = "DENY"
    if "Access-Control-Allow-Private-Network" in response.headers:
        del response.headers["Access-Control-Allow-Private-Network"]
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"


app = create_app()
