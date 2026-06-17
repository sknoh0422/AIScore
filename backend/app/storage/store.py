"""L5 저장소: 업로드/결과/잡 메타. 1단계는 인메모리 레지스트리 + 파일."""
from __future__ import annotations
import uuid
from pathlib import Path
from app.orchestration.job import Job

DATA_ROOT = Path("data/jobs")

class JobStore:
    def __init__(self, root: Path = DATA_ROOT) -> None:
        self._root = Path(root)
        self._jobs: dict[str, Job] = {}

    def new_job_dir(self) -> tuple[str, Path]:
        job_id = uuid.uuid4().hex
        d = self._root / job_id
        d.mkdir(parents=True, exist_ok=True)
        return job_id, d

    def save(self, job: Job) -> None: self._jobs[job.id] = job
    def get(self, job_id: str) -> Job | None: return self._jobs.get(job_id)

    def reset(self, root: Path | None = None) -> None:
        self._jobs.clear()
        if root is not None:
            self._root = Path(root)

store = JobStore()
