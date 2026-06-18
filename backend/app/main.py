"""AIScore FastAPI 진입점 (L1)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.jobs import router as jobs_router

app = FastAPI(title="AIScore")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)
