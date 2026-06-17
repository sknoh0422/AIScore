"""L2 런타임 파이프라인 오케스트레이터(1단계): SVS 4성부 병렬."""
from __future__ import annotations
from pathlib import Path
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor
from app.domain.ports import OmrPort, ScoreParserPort, SvsPort, MixerPort
from app.domain.score import VoiceName
from app.orchestration.job import Job, JobStatus

class Stage1Orchestrator:
    def __init__(self, omr: OmrPort, parser: ScoreParserPort, svs: SvsPort, mixer: MixerPort):
        self.omr, self.parser, self.svs, self.mixer = omr, parser, svs, mixer

    def run(self, job_id: str, image_path: Path, work_dir: Path,
            on_update: Optional[Callable[[Job], None]] = None) -> Job:
        job = Job(id=job_id)
        work_dir = Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)

        def advance(status: JobStatus) -> None:
            job.status = status
            if on_update:
                on_update(job)

        def fail(stage: JobStatus, reason: str) -> Job:
            job.fail(stage, reason)
            if on_update:
                on_update(job)
            return job

        try:
            advance(JobStatus.OMR)
            musicxml = self.omr.recognize(image_path)
        except Exception as e:
            return fail(JobStatus.OMR, str(e))
        try:
            advance(JobStatus.PARSING)
            score = self.parser.parse(musicxml)
        except Exception as e:
            return fail(JobStatus.PARSING, str(e))
        try:
            advance(JobStatus.SYNTH)
            # score.voices 에 실제 존재하는 성부만 합성 (N-voice 강건성)
            present = [v for v in VoiceName if v in score.voices]
            def synth(v: VoiceName) -> Path:
                return self.svs.synthesize(score, v, work_dir / f"{v.value}.wav")
            with ThreadPoolExecutor(max_workers=4) as ex:
                wavs = list(ex.map(synth, present))
        except Exception as e:
            return fail(JobStatus.SYNTH, str(e))
        try:
            advance(JobStatus.MIXING)
            result = self.mixer.mix(wavs, work_dir / "choir.wav")
        except Exception as e:
            return fail(JobStatus.MIXING, str(e))
        job.result_path = str(result)
        advance(JobStatus.DONE)
        return job
