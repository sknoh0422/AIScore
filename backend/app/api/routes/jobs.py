"""L1 잡 엔드포인트."""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from app.api.schemas import JobCreated, JobState
from app.storage.store import store
from app.orchestration.job import Job, JobStatus
from app.orchestration.orchestrator import Stage1Orchestrator
from app.stages.omr.oemer_adapter import OemerAdapter
from app.stages.parsing.music21_parser import Music21Parser
from app.stages.svs.vowel_synth_adapter import VowelSynthAdapter
from app.stages.mixing.mixer import Mixer

router = APIRouter()

def _orchestrator() -> Stage1Orchestrator:
    return Stage1Orchestrator(OemerAdapter(), Music21Parser(), VowelSynthAdapter(), Mixer())

def _run(job_id: str, image_path: Path, work_dir: Path) -> None:
    _orchestrator().run(job_id, image_path, work_dir, on_update=store.save)

@router.post("/jobs", response_model=JobCreated, status_code=201)
async def create_job(background: BackgroundTasks, file: UploadFile = File(...)) -> JobCreated:
    job_id, work_dir = store.new_job_dir()
    image_path = work_dir / "input.png"
    image_path.write_bytes(await file.read())
    store.save(Job(id=job_id, status=JobStatus.QUEUED))
    background.add_task(_run, job_id, image_path, work_dir)
    return JobCreated(id=job_id)

@router.get("/jobs/{job_id}", response_model=JobState)
def get_job(job_id: str) -> JobState:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return JobState(id=job.id, status=job.status.value,
                    failed_stage=job.failed_stage.value if job.failed_stage else None,
                    error=job.error, result_path=job.result_path)
