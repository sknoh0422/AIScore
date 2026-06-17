"""AIScore FastAPI 진입점 (L1)."""
from fastapi import FastAPI
from app.api.routes.jobs import router as jobs_router

app = FastAPI(title="AIScore")
app.include_router(jobs_router)
