"""L1 Pydantic 스키마."""
from __future__ import annotations
from pydantic import BaseModel

class JobCreated(BaseModel):
    id: str

class JobState(BaseModel):
    id: str
    status: str
    failed_stage: str | None = None
    error: str | None = None
    result_path: str | None = None
    score_path: str | None = None
    voice_paths: dict[str, str] = {}
    timing_path: str | None = None
