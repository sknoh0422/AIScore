"""Task 6: 존재하는 성부만 합성 — N-voice 강건성 테스트."""
from pathlib import Path
import soundfile as sf, numpy as np
from app.domain.score import Score, Voice, Note, VoiceName
from app.orchestration.orchestrator import Stage1Orchestrator
from app.orchestration.job import JobStatus


class Omr:
    def recognize(self, p): return Path("x.musicxml")


class Parser2:
    def parse(self, p):
        # 소프라노 + 베이스만 존재 (알토·테너 없음)
        return Score(voices={
            VoiceName.SOPRANO: Voice(VoiceName.SOPRANO, [Note("A4", 1.0)]),
            VoiceName.BASS:    Voice(VoiceName.BASS,    [Note("F3", 1.0)]),
        })


class Svs:
    def synthesize(self, score, voice, out):
        sf.write(out, np.zeros(100, dtype=np.float32), 44100)
        return out


class Mix:
    def mix(self, wavs, out):
        # 정확히 2개 성부만 전달됐는지 검증
        assert len(wavs) == 2
        sf.write(out, np.zeros(100, dtype=np.float32), 44100)
        return out


def test_synthesizes_only_present_voices(tmp_path):
    """소프라노·베이스만 있는 악보에서 DONE 이고 wav 가 2개임을 확인."""
    job = Stage1Orchestrator(Omr(), Parser2(), Svs(), Mix()).run(
        "j", Path("x.png"), tmp_path
    )
    assert job.status == JobStatus.DONE
