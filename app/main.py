import os
import secrets
import time
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import db, erp, service


def create_app(engine=None):
    engine = engine or db.make_engine()
    app = FastAPI(title="Matchbook Invoice Automation", version="0.1.0")
    app.state.engine = engine
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def guards(request: Request, call_next):
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Invalid content length."}, status_code=400)
            if length > 10 * 1024 * 1024 + 65536:
                return JSONResponse({"detail": "Request exceeds the 10 MB document limit."}, status_code=413)
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Cross-origin mutation rejected."}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site mutation rejected."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        # FastAPI's built-in Swagger page loads its UI bundle from jsDelivr and
        # initializes it with a small inline script. Keep that exception scoped
        # to the documentation page; the application itself remains self-only.
        if request.url.path == "/docs":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' blob: https://fastapi.tiangolo.com; connect-src 'self'; "
                "frame-ancestors 'none'; object-src 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'"
            )
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(service.Conflict)
    async def conflict(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(_request, _exc):
        return JSONResponse({"detail": "Invoice not found."}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(_request, exc):
        from pydantic import ValidationError

        message = (
            "Check required fields, ISO date and decimal amounts."
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        return JSONResponse({"detail": message}, status_code=422)

    def user(request: Request):
        token = request.cookies.get("matchbook_session", "")
        with engine.connect() as conn:
            role = conn.execute(
                select(db.sessions.c.role).where(
                    db.sessions.c.id == token, db.sessions.c.expires > time.time()
                )
            ).scalar()
        if role is None:
            raise HTTPException(401, "Sign in to continue. Your unsaved edits have not been submitted.")
        return role

    def reviewer(role=Depends(user)):
        if role != "reviewer":
            raise HTTPException(403, "Reviewer access is required for this action.")
        return role

    @app.get("/api/auth")
    def auth_info():
        return {"demo": os.getenv("MATCHBOOK_DEMO_AUTH", "1") == "1"}

    @app.post("/api/login")
    def login(body: Login, response: Response):
        if body.role not in ("viewer", "reviewer"):
            raise HTTPException(422, "Choose viewer or reviewer.")
        if os.getenv("MATCHBOOK_DEMO_AUTH", "1") != "1":
            expected = os.getenv("MATCHBOOK_" + body.role.upper() + "_PASSWORD", "")
            if not expected or not secrets.compare_digest(expected, body.password):
                raise HTTPException(401, "Invalid credentials.")
        token = secrets.token_urlsafe(40)
        with engine.begin() as conn:
            conn.execute(delete(db.sessions).where(db.sessions.c.expires < time.time()))
            conn.execute(
                db.sessions.insert().values(id=token, role=body.role, expires=time.time() + 8 * 3600)
            )
        response.set_cookie(
            "matchbook_session",
            token,
            httponly=True,
            samesite="strict",
            max_age=8 * 3600,
            secure=os.getenv("MATCHBOOK_SECURE_COOKIE") == "1",
        )
        return {"role": body.role}

    @app.post("/api/logout")
    def logout(request: Request, response: Response):
        with engine.begin() as conn:
            conn.execute(
                delete(db.sessions).where(db.sessions.c.id == request.cookies.get("matchbook_session", ""))
            )
        response.delete_cookie("matchbook_session")
        return {"ok": True}

    @app.get("/api/me")
    def me(role=Depends(user)):
        return {"role": role, "demo": os.getenv("MATCHBOOK_DEMO_AUTH", "1") == "1"}

    @app.get("/api/invoices")
    def invoices(q: str = "", status: str = "", page: int = 1, _role=Depends(user)):
        return service.queue(engine, q[:150], status, max(1, page))

    @app.get("/api/invoices/{document_id}")
    def invoice(document_id: str, _role=Depends(user)):
        return service.get_document(engine, document_id)

    @app.post("/api/invoices")
    async def upload(file: UploadFile = File(...), mode: str = Form("local"), role=Depends(reviewer)):
        if mode not in ("local", "replay"):
            raise HTTPException(422, "Choose local or replay extraction.")
        content = await file.read(10 * 1024 * 1024 + 1)
        doc_id, duplicate = service.intake(engine, content, file.filename or "document", mode, role)
        return {"id": doc_id, "duplicate": duplicate}

    @app.post("/api/invoices/{document_id}/actions/{action}")
    def action(document_id: str, action: str, body: Mutation, role=Depends(reviewer)):
        return service.mutate(engine, document_id, body.version, action, role, body.payload)

    @app.get("/api/invoices/{document_id}/pages/{page}")
    def preview(document_id: str, page: int, _role=Depends(user)):
        with engine.connect() as conn:
            row = (
                conn.execute(
                    select(db.documents.c.path, db.documents.c.pages).where(db.documents.c.id == document_id)
                )
                .mappings()
                .first()
            )
        if not row or not 1 <= page <= (row["pages"] or 0):
            raise HTTPException(404, "Page not available yet.")
        path = Path(row["path"]).parent / "pages" / f"{page}.png"
        if not path.exists():
            raise HTTPException(404, "Page preview unavailable. Original remains available.")
        return FileResponse(path, media_type="image/png")

    @app.get("/api/invoices/{document_id}/original")
    def original(document_id: str, _role=Depends(user)):
        with engine.connect() as conn:
            row = (
                conn.execute(
                    select(db.documents.c.path, db.documents.c.filename).where(
                        db.documents.c.id == document_id
                    )
                )
                .mappings()
                .first()
            )
        if not row:
            raise HTTPException(404, "Document not found.")
        return FileResponse(row["path"], filename=row["filename"])

    @app.get("/api/invoices/{document_id}/export")
    def export(document_id: str, _role=Depends(user)):
        obj = service.get_document(engine, document_id)
        return JSONResponse(
            obj, headers={"Content-Disposition": 'attachment; filename="matchbook-evidence.json"'}
        )

    @app.get("/api/orders")
    def order_list(_role=Depends(user)):
        with engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(db.orders).limit(100)).mappings()]

    @app.get("/api/drafts")
    def drafts(_role=Depends(user)):
        with engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(db.sandbox_drafts).order_by(db.sandbox_drafts.c.created.desc()).limit(100)
                ).mappings()
            ]

    @app.post("/api/invoices/{document_id}/reconcile")
    def reconcile(document_id: str, body: Mutation, role=Depends(reviewer)):
        obj = service.get_document(engine, document_id)
        if obj["status"] != "sync_uncertain" or obj["version"] != body.version:
            raise service.Conflict("Only the current uncertain sync can be reconciled.")
        reference = f"mb-{document_id}-r{obj['revision']}"
        try:
            name = erp.reconcile(engine, reference)
        except Exception:
            raise HTTPException(503, "Destination unavailable. No additional write was attempted.") from None
        if not name:
            raise service.Conflict(
                "No unique draft found. The invoice stays on hold; no new write was attempted."
            )
        with engine.begin() as conn:
            result = conn.execute(
                update(db.documents)
                .where(db.documents.c.id == document_id, db.documents.c.version == body.version)
                .values(status="synced", remote_id=name, error=None, version=body.version + 1)
            )
            if result.rowcount != 1:
                raise service.Conflict("Invoice changed during reconciliation.")
            conn.execute(
                update(db.syncs)
                .where(db.syncs.c.reference == reference)
                .values(state="synced", remote_id=name)
            )
            db.audit(
                conn,
                document_id,
                "Existing draft reconciled",
                role,
                name + "; read-only lookup, no new write.",
            )
        return service.get_document(engine, document_id)

    @app.get("/api/system")
    def system(_role=Depends(user)):
        with engine.connect() as conn:
            last_seen = conn.execute(select(func.max(db.heartbeats.c.seen))).scalar()
            active = conn.execute(
                select(func.count())
                .select_from(db.jobs)
                .where(db.jobs.c.state == "running", db.jobs.c.lease_until > time.time())
            ).scalar()
            counts = dict(conn.execute(select(db.jobs.c.state, func.count()).group_by(db.jobs.c.state)).all())
        try:
            with httpx.Client(timeout=1.5) as client:
                llm = client.get(os.getenv("LLM_BASE_URL", "http://127.0.0.1:8091/v1") + "/models").is_success
        except Exception:
            llm = False
        return dict(
            erp_mode=erp.mode(),
            database=engine.dialect.name,
            llm_online=llm,
            model=os.getenv("LLM_MODEL", "Qwen3 0.6B · Q8 weights / Transformers CPU"),
            worker_online=bool(active or (last_seen and time.time() - last_seen < 10)),
            jobs=counts,
            demo_auth=os.getenv("MATCHBOOK_DEMO_AUTH", "1") == "1",
            erp_verified=False,
            build="0.1.0",
        )

    static = db.ROOT / "frontend" / "dist"
    if static.exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(static / "index.html")

    return app


class Login(BaseModel):
    role: str = "reviewer"
    password: str = Field(default="", max_length=200)


class Mutation(BaseModel):
    version: int = Field(ge=1)
    payload: dict | None = None


app = create_app()
