"""L2 런타임 파이프라인 오케스트레이터(1단계): SVS 4성부 병렬."""
from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app.domain.ports import OmrPort, ScoreParserPort, SvsPort, MixerPort
from app.domain.score import VoiceName
from app.orchestration.job import Job, JobStatus

class Stage1Orchestrator:
    def __init__(self, omr: OmrPort, parser: ScoreParserPort, svs: SvsPort, mixer: MixerPort):
        self.omr, self.parser, self.svs, self.mixer = omr, parser, svs, mixer

    def run(self, job_id: str, image_path: Path, work_dir: Path) -> Job:
        job = Job(id=job_id)
        work_dir = Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)
        try:
            job.status = JobStatus.OMR
            musicxml = self.omr.recognize(image_path)
        except Exception as e:
            job.fail(JobStatus.OMR, str(e)); return job
        try:
            job.status = JobStatus.PARSING
            score = self.parser.parse(musicxml)
        except Exception as e:
            job.fail(JobStatus.PARSING, str(e)); return job
        try:
            job.status = JobStatus.SYNTH
            def synth(v: VoiceName) -> Path:
                return self.svs.synthesize(score, v, work_dir / f"{v.value}.wav")
            with ThreadPoolExecutor(max_workers=4) as ex:
                wavs = list(ex.map(synth, list(VoiceName)))
        except Exception as e:
            job.fail(JobStatus.SYNTH, str(e)); return job
        try:
            job.status = JobStatus.MIXING
            result = self.mixer.mix(wavs, work_dir / "choir.wav")
        except Exception as e:
            job.fail(JobStatus.MIXING, str(e)); return job
        job.status = JobStatus.DONE
        job.result_path = str(result)
        return job
