from pathlib import Path
import soundfile as sf, numpy as np
from app.domain.score import Score, Voice, Note, VoiceName
from app.orchestration.orchestrator import Stage1Orchestrator
from app.orchestration.job import JobStatus

class FakeOmr:
    def recognize(self, image_path): return Path("dummy.musicxml")
class FakeParser:
    def parse(self, p):
        return Score(voices={v: Voice(v, [Note("A4", 1.0)]) for v in VoiceName})
class FakeSvs:
    def synthesize(self, score, voice, out_path):
        sf.write(out_path, np.zeros(100, dtype=np.float32), 44100); return out_path
class FakeMixer:
    def mix(self, wavs, out_path):
        sf.write(out_path, np.zeros(100, dtype=np.float32), 44100); return out_path

def test_pipeline_runs_to_done(tmp_path):
    orch = Stage1Orchestrator(FakeOmr(), FakeParser(), FakeSvs(), FakeMixer())
    job = orch.run(job_id="j1", image_path=Path("x.png"), work_dir=tmp_path)
    assert job.status == JobStatus.DONE
    assert Path(job.result_path).exists()

def test_pipeline_fails_on_omr_error(tmp_path):
    class BoomOmr:
        def recognize(self, p): raise RuntimeError("boom")
    orch = Stage1Orchestrator(BoomOmr(), FakeParser(), FakeSvs(), FakeMixer())
    job = orch.run(job_id="j2", image_path=Path("x.png"), work_dir=tmp_path)
    assert job.status == JobStatus.FAILED
    assert job.failed_stage == JobStatus.OMR

def test_status_updates_are_observed(tmp_path):
    seen = []
    orch = Stage1Orchestrator(FakeOmr(), FakeParser(), FakeSvs(), FakeMixer())
    job = orch.run("j3", Path("x.png"), tmp_path, on_update=lambda j: seen.append(j.status))
    assert JobStatus.OMR in seen
    assert JobStatus.SYNTH in seen
    assert seen[-1] == JobStatus.DONE
