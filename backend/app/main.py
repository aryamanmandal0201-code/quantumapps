import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from .bootstrap import enable_row_level_security, ensure_admin
from .config import get_settings
from .database import Base, engine
from .routers import admin, auth, chat, tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("taskpilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.jwt_secret == "dev-only-secret-change-me":
        log.warning("JWT_SECRET is not set; using an insecure development secret.")
    Base.metadata.create_all(bind=engine)
    enable_row_level_security()
    ensure_admin()
    yield


app = FastAPI(
    title="TaskPilot API",
    description="Task manager driven by an AI agent with tool calling. Log in with the Authorize button (username = email).",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OperationalError)
async def database_unavailable(request: Request, exc: OperationalError):
    log.error("Database error: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "The database is unavailable right now. Please try again shortly."})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Please try again."})


app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(chat.router)
app.include_router(admin.router)


@app.get("/", tags=["meta"])
def root():
    return {"name": "TaskPilot API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
