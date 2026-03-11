from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from api.routers import ed, patients, pcp, chat, Health as health
from api.dependencies import init_services, shutdown_services
from config.logging import setup_logging


logger = logging.getLogger("BriefMD API")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_services()
    yield
    shutdown_services()


app = FastAPI(
    title="BriefMD API",
    description="Clinical intelligence and quality — discharge summary verification",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request timing middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.3f}s"
    if elapsed > 10:
        logger.warning(f"Slow request: {request.url.path} took {elapsed:.1f}s")
    return response
# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Check server logs.",
        },
    )
# --- Register all routers ---
app.include_router(health.router,    prefix="/api/v1",       tags=["Health"])
app.include_router(patients.router,  prefix="/api/v1",       tags=["Patients"])
app.include_router(ed.router,        prefix="/api/v1/ed",    tags=["ED Quality Gate"])
app.include_router(pcp.router,       prefix="/api/v1/pcp",   tags=["PCP Report"])
app.include_router(chat.router,      prefix="/api/v1/chat",  tags=["RAG Chat"])

@app.get("/health")
async def health():
    return {"status": "ok"}
