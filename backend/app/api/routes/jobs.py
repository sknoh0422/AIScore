"""L1 잡 엔드포인트."""
from __future__ import annotations
import io
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from app.api.schemas import JobCreated, JobState
from app.storage.store import store
from app.orchestration.job import Job, JobStatus
from app.orchestration.orchestrator import Stage1Orchestrator
from app.stages.omr.audiveris_adapter import AudiverisAdapter
from app.stages.parsing.music21_parser import Music21Parser
from app.stages.svs.vowel_synth_adapter import VowelSynthAdapter
from app.stages.mixing.mixer import Mixer

_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/tiff"}
_MAX_BYTES = 20 * 1024 * 1024

router = APIRouter()

def _run(job_id: str, image_path: Path, work_dir: Path) -> None:
    orch = Stage1Orchestrator(
        AudiverisAdapter(work_dir=work_dir / "omr"),
        Music21Parser(), VowelSynthAdapter(), Mixer())
    orch.run(job_id, image_path, work_dir, on_update=store.save)

@router.post("/jobs", response_model=JobCreated, status_code=201)
async def create_job(background: BackgroundTasks, file: UploadFile = File(...)) -> JobCreated:
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(415, f"지원하지 않는 형식: {file.content_type}")
    data = await file.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, "파일 크기 초과 (최대 20MB)")
    try:
        Image.open(io.BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "유효한 이미지 파일이 아님")
    job_id, work_dir = store.new_job_dir()
    image_path = work_dir / "input.png"      # UUID 디렉터리 + 고정명 → traversal 차단
    image_path.write_bytes(data)
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
                    error=job.error, result_path=job.result_path,
                    score_path=job.score_path)

@router.get("/jobs/{job_id}/audio")
def get_audio(job_id: str) -> FileResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if not job.result_path or not Path(job.result_path).exists():
        raise HTTPException(404, "음원 미생성")
    return FileResponse(job.result_path, media_type="audio/wav")

@router.get("/jobs/{job_id}/score")
def get_score(job_id: str) -> FileResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if not job.score_path or not Path(job.score_path).exists():
        raise HTTPException(404, "악보 미생성")
    return FileResponse(job.score_path, media_type="application/vnd.recordare.musicxml+xml")
