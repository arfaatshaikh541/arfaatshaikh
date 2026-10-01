from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.hardening import MAX_BODY_BYTES, SecurityHeadersMiddleware, unhandled_error_handler


def make_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/api/v1/auth/me")
    async def me():
        return {"ok": True}

    @app.get("/api/v1/quran/surahs")
    async def public():
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail: postgresql://user:pw@host/db")

    @app.post("/echo")
    async def echo():
        return {"ok": True}
    return app


async def test_headers_and_no_store_on_sensitive_paths():
    async with AsyncClient(transport=ASGITransport(app=make_app()), base_url="http://t") as c:
        sensitive = await c.get("/api/v1/auth/me")
        public = await c.get("/api/v1/quran/surahs")
    assert sensitive.headers["x-content-type-options"] == "nosniff" and sensitive.headers["cache-control"] == "no-store"
    assert public.headers["referrer-policy"] == "no-referrer" and "cache-control" not in public.headers


async def test_internal_errors_do_not_leak_details():
    async with AsyncClient(transport=ASGITransport(app=make_app(), raise_app_exceptions=False), base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 500 and "postgresql" not in r.text and "secret" not in r.text
    assert r.json()["error"]["code"] == "internal_error"


async def test_oversized_bodies_are_rejected_before_processing():
    async with AsyncClient(transport=ASGITransport(app=make_app()), base_url="http://t") as c:
        r = await c.post("/echo", headers={"content-length": str(MAX_BODY_BYTES + 1)}, content=b"x")
    assert r.status_code == 413
