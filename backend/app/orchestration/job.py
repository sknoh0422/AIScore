"""L2 잡 상태 모델: queued→omr→parsing→synth→mixing→done/failed."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"; OMR = "omr"; PARSING = "parsing"
    SYNTH = "synth"; MIXING = "mixing"; DONE = "done"; FAILED = "failed"

@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.QUEUED
    failed_stage: JobStatus | None = None
    error: str | None = None
    result_path: str | None = None

    def fail(self, stage: JobStatus, reason: str) -> None:
        self.status = JobStatus.FAILED
        self.failed_stage = stage
        self.error = reason
