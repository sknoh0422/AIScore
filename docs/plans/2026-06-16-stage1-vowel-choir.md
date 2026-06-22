# 1단계: 모음 "우" 합창 파이프라인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 악보 이미지를 업로드하면 4성부(SATB)를 모음 "우"로 합성해 합창 WAV를 반환하는 end-to-end 수직 슬라이스를 만든다.

**Architecture:** 헥사고날. 모든 단계는 `backend/app/domain/ports.py`(동결됨)의 Protocol을 구현하는 어댑터. 오케스트레이터는 포트에만 의존. 가사/OCR/정렬은 1단계 범위 밖(`[2단계]`).

**Tech Stack:** Python 3.10 (conda `aiscore`), pytest, numpy, soundfile, music21, oemer(CLI), FastAPI. 디바이스는 `core/device.py`만 사용.

**참조:** 설계 문서 `docs/superpowers/specs/2026-06-16-aiscore-design.md`, 규약 `CLAUDE.md`.

**테스트 규칙:** 빠른 단위테스트는 기본. 느린 외부 의존(oemer, e2e)은 `@pytest.mark.integration` 으로 분리.

---

## 파일 구조 (이 계획에서 생성/수정)

| 파일 | 책임 |
|---|---|
| `backend/pyproject.toml` | pytest 설정, marker 등록 |
| `backend/app/domain/score.py` | (수정) `to_midi` 헬퍼 — 음이름→MIDI |
| `backend/app/stages/svs/vowel_synth_adapter.py` | 한 성부 → "우" 톤 WAV (SvsPort) |
| `backend/app/stages/mixing/mixer.py` | 4 WAV → 합창 WAV (MixerPort) |
| `backend/app/stages/parsing/music21_parser.py` | MusicXML → Score, SATB 분리 (ScoreParserPort) |
| `backend/app/stages/omr/oemer_adapter.py` | 이미지 → MusicXML (OmrPort, oemer CLI 래퍼) |
| `backend/app/orchestration/job.py` | 잡 상태 모델 |
| `backend/app/storage/store.py` | 잡 디렉터리/파일 저장 |
| `backend/app/orchestration/orchestrator.py` | 1단계 파이프라인 조립 (포트 의존) |
| `backend/app/api/schemas.py`, `routes/jobs.py`, `main.py` | FastAPI 엔드포인트 |
| `backend/tests/**` | 각 단위/통합 테스트 |

---

## Task 1: 테스트 하니스 + 도메인 MIDI 헬퍼

**Files:**
- Create: `backend/pyproject.toml`
- Modify: `backend/app/domain/score.py`
- Test: `backend/tests/test_score.py`

- [ ] **Step 1: pyproject 작성 (pytest marker)**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["integration: 느린 외부 의존 테스트 (oemer, e2e)"]
```

- [ ] **Step 2: 실패 테스트 작성**

```python
# backend/tests/test_score.py
from app.domain.score import Note, to_midi

def test_to_midi_a4_is_69():
    assert to_midi("A4") == 69

def test_to_midi_sharp():
    assert to_midi("C#4") == 61

def test_rest_pitch_is_none():
    assert Note(pitch=None, quarter_length=1.0).pitch is None
```

- [ ] **Step 3: 실패 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_score.py -v`
Expected: FAIL — `cannot import name 'to_midi'`

- [ ] **Step 4: `to_midi` 구현 (score.py 끝에 추가)**

```python
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

def to_midi(pitch: str) -> int:
    """음이름("C4","G#3","Bb4") → MIDI 번호. A4=69."""
    name = pitch[0].upper()
    i = 1
    semitone = _PC[name]
    while i < len(pitch) and pitch[i] in "#b":
        semitone += 1 if pitch[i] == "#" else -1
        i += 1
    octave = int(pitch[i:])
    return 12 * (octave + 1) + semitone
```

- [ ] **Step 5: 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_score.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/domain/score.py backend/tests/test_score.py
git commit -m "feat(domain): add to_midi helper + pytest harness"
```

---

## Task 2: VowelSynthAdapter — 한 성부를 "우"로 합성

**Files:**
- Modify: `backend/app/stages/svs/vowel_synth_adapter.py`
- Test: `backend/tests/test_vowel_synth.py`

**설계:** 음표 시퀀스를 sine+배음 톤으로 합성(모음 "우" 근사). 템포는 상수 `DEFAULT_BPM=80`. 쉼표(pitch=None)는 무음. 출력 44.1kHz mono WAV.

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_vowel_synth.py
import soundfile as sf
from pathlib import Path
from app.domain.score import Score, Voice, Note, VoiceName
from app.stages.svs.vowel_synth_adapter import VowelSynthAdapter, SAMPLE_RATE, DEFAULT_BPM

def _score():
    v = Voice(name=VoiceName.SOPRANO, notes=[Note("A4", 1.0), Note(None, 1.0), Note("C5", 2.0)])
    return Score(voices={VoiceName.SOPRANO: v})

def test_synth_creates_wav_of_expected_length(tmp_path):
    out = tmp_path / "s.wav"
    VowelSynthAdapter().synthesize(_score(), VoiceName.SOPRANO, out)
    data, sr = sf.read(out)
    assert sr == SAMPLE_RATE
    expected_sec = (1.0 + 1.0 + 2.0) * (60.0 / DEFAULT_BPM)
    assert abs(len(data) / sr - expected_sec) < 0.05

def test_rest_is_silent(tmp_path):
    out = tmp_path / "s.wav"
    v = Voice(name=VoiceName.BASS, notes=[Note(None, 1.0)])
    VowelSynthAdapter().synthesize(Score(voices={VoiceName.BASS: v}), VoiceName.BASS, out)
    data, _ = sf.read(out)
    assert float(abs(data).max()) < 1e-6
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_vowel_synth.py -v`
Expected: FAIL — import error (클래스 미구현)

- [ ] **Step 3: 구현**

```python
# backend/app/stages/svs/vowel_synth_adapter.py
"""L3 SVS(1단계): 모음 '우' 합성. SvsPort 구현."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import soundfile as sf
from app.domain.score import Score, VoiceName, to_midi

SAMPLE_RATE = 44_100
DEFAULT_BPM = 80
_HARMONICS = [(1, 1.0), (2, 0.25), (3, 0.12)]  # "우" 근사: 낮은 배음 위주

def _freq(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)

def _tone(freq: float, n: int) -> np.ndarray:
    t = np.arange(n) / SAMPLE_RATE
    wave = sum(amp * np.sin(2 * np.pi * freq * h * t) for h, amp in _HARMONICS)
    env = np.ones(n)
    fade = min(int(0.01 * SAMPLE_RATE), n // 2)  # 클릭 방지 페이드
    if fade:
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
    return (wave * env).astype(np.float32)

class VowelSynthAdapter:
    def __init__(self, bpm: int = DEFAULT_BPM) -> None:
        self.bpm = bpm

    def synthesize(self, score: Score, voice: VoiceName, out_path: Path) -> Path:
        notes = score.voices[voice].notes
        sec_per_quarter = 60.0 / self.bpm
        segments = []
        for note in notes:
            n = int(note.quarter_length * sec_per_quarter * SAMPLE_RATE)
            if note.pitch is None:
                segments.append(np.zeros(n, dtype=np.float32))
            else:
                segments.append(_tone(_freq(to_midi(note.pitch)), n) * 0.3)
        audio = np.concatenate(segments) if segments else np.zeros(1, dtype=np.float32)
        sf.write(out_path, audio, SAMPLE_RATE)
        return out_path
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_vowel_synth.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/stages/svs/vowel_synth_adapter.py backend/tests/test_vowel_synth.py
git commit -m "feat(svs): vowel '우' synth adapter (stage 1)"
```

---

## Task 3: Mixer — 4 WAV 합치기

**Files:**
- Modify: `backend/app/stages/mixing/mixer.py`
- Test: `backend/tests/test_mixer.py`

**설계:** 길이가 다른 WAV는 최장 길이에 zero-pad, 합산 후 클리핑 방지 정규화.

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_mixer.py
import numpy as np, soundfile as sf
from app.stages.mixing.mixer import Mixer

def _wav(p, n, val=0.5):
    sf.write(p, np.full(n, val, dtype=np.float32), 44100)

def test_mix_pads_to_longest_and_normalizes(tmp_path):
    a, b, out = tmp_path/"a.wav", tmp_path/"b.wav", tmp_path/"mix.wav"
    _wav(a, 1000); _wav(b, 2000)
    Mixer().mix([a, b], out)
    data, sr = sf.read(out)
    assert sr == 44100
    assert len(data) == 2000
    assert float(abs(data).max()) <= 1.0
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_mixer.py -v`
Expected: FAIL — import error

- [ ] **Step 3: 구현**

```python
# backend/app/stages/mixing/mixer.py
"""L3 믹싱: 성부별 WAV → 합창 WAV. MixerPort 구현."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import soundfile as sf

class Mixer:
    def mix(self, voice_wavs: list[Path], out_path: Path) -> Path:
        arrays = [sf.read(p)[0].astype(np.float32) for p in voice_wavs]
        if not arrays:
            raise ValueError("mix: 빈 입력")
        length = max(len(a) for a in arrays)
        acc = np.zeros(length, dtype=np.float32)
        for a in arrays:
            acc[:len(a)] += a
        peak = float(abs(acc).max())
        if peak > 1.0:
            acc /= peak
        sf.write(out_path, acc, 44_100)
        return out_path
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_mixer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/stages/mixing/mixer.py backend/tests/test_mixer.py
git commit -m "feat(mixing): mix 4 voice WAVs with pad + normalize"
```

---

## Task 4: Music21Parser — MusicXML → Score (SATB)

**Files:**
- Modify: `backend/app/stages/parsing/music21_parser.py`
- Test: `backend/tests/test_parser.py`, `backend/tests/fixtures/satb_min.musicxml`

**설계:** music21로 파트를 읽어 순서대로 S/A/T/B에 매핑(파트 4개 가정). 화음은 최상단 음만 취함(1단계 단순화). 가사는 무시.

- [ ] **Step 1: 최소 MusicXML 픽스처 생성**

`backend/tests/fixtures/satb_min.musicxml` — 4파트, 각 파트에 음표 1~2개의 최소 SATB. (music21로 생성: 아래 스크립트를 1회 실행해 픽스처를 만든 뒤 커밋)

```python
# 픽스처 생성 1회용 (커밋 대상은 생성된 .musicxml)
from music21 import stream, note
s = stream.Score()
for nm, p in [("S","A4"),("A","F4"),("T","C4"),("B","F3")]:
    part = stream.Part(); part.id = nm
    part.append(note.Note(p, quarterLength=2.0))
    s.insert(0, part)
s.write("musicxml", "backend/tests/fixtures/satb_min.musicxml")
```

- [ ] **Step 2: 실패 테스트**

```python
# backend/tests/test_parser.py
from pathlib import Path
from app.stages.parsing.music21_parser import Music21Parser
from app.domain.score import VoiceName

FIX = Path(__file__).parent / "fixtures" / "satb_min.musicxml"

def test_parse_produces_four_voices():
    score = Music21Parser().parse(FIX)
    assert set(score.voices) == set(VoiceName)
    assert score.voices[VoiceName.SOPRANO].notes[0].pitch == "A4"
    assert score.voices[VoiceName.BASS].notes[0].pitch == "F3"
```

- [ ] **Step 3: 실패 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_parser.py -v`
Expected: FAIL — import error

- [ ] **Step 4: 구현**

```python
# backend/app/stages/parsing/music21_parser.py
"""L3 파싱: MusicXML → 내부 Score, SATB 분리. ScoreParserPort 구현."""
from __future__ import annotations
from pathlib import Path
from music21 import converter, stream, note as m21note
from app.domain.score import Score, Voice, Note, VoiceName

_ORDER = [VoiceName.SOPRANO, VoiceName.ALTO, VoiceName.TENOR, VoiceName.BASS]

class Music21Parser:
    def parse(self, musicxml_path: Path) -> Score:
        parsed = converter.parse(str(musicxml_path))
        parts = list(parsed.getElementsByClass(stream.Part))
        voices: dict[VoiceName, Voice] = {}
        for vn, part in zip(_ORDER, parts):
            notes: list[Note] = []
            for el in part.recurse().notesAndRests:
                ql = float(el.duration.quarterLength)
                if isinstance(el, m21note.Rest):
                    notes.append(Note(pitch=None, quarter_length=ql))
                elif isinstance(el, m21note.Note):
                    notes.append(Note(pitch=el.pitch.nameWithOctave, quarter_length=ql))
                else:  # Chord → 최상단 음 (1단계 단순화)
                    top = max(el.pitches, key=lambda p: p.midi)
                    notes.append(Note(pitch=top.nameWithOctave, quarter_length=ql))
            voices[vn] = Voice(name=vn, notes=notes)
        return Score(voices=voices)
```

- [ ] **Step 5: 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_parser.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/stages/parsing/music21_parser.py backend/tests/test_parser.py backend/tests/fixtures/satb_min.musicxml
git commit -m "feat(parsing): MusicXML -> SATB Score via music21"
```

---

## Task 5: OemerAdapter — 이미지 → MusicXML (통합)

**Files:**
- Modify: `backend/app/stages/omr/oemer_adapter.py`
- Test: `backend/tests/test_oemer_adapter.py`

**설계:** oemer CLI를 subprocess로 호출. oemer는 입력 이미지 폴더에 `<name>.musicxml` 생성. 실패 시 `OmrError` 발생(조용한 실패 금지, 규칙 C12). 실제 실행은 느려 `@pytest.mark.integration`.

- [ ] **Step 1: 실패 테스트 (통합 + 단위)**

```python
# backend/tests/test_oemer_adapter.py
import pytest
from pathlib import Path
from app.stages.omr.oemer_adapter import OemerAdapter
from app.core.errors import OmrError

def test_missing_image_raises(tmp_path):
    with pytest.raises(OmrError):
        OemerAdapter().recognize(tmp_path / "nope.png")

@pytest.mark.integration
def test_recognize_sample_produces_musicxml():
    img = Path(__file__).parents[2] / "score_images" / "온맘다해.png"
    out = OemerAdapter().recognize(img)
    assert out.exists() and out.suffix == ".musicxml"
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_oemer_adapter.py::test_missing_image_raises -v`
Expected: FAIL — import error

- [ ] **Step 3: 에러 타입 정의 (errors.py)**

```python
# backend/app/core/errors.py  (스텁 교체)
"""도메인 예외 정의."""
class PipelineError(Exception): ...
class OmrError(PipelineError): ...
class SynthError(PipelineError): ...
```

- [ ] **Step 4: 어댑터 구현**

```python
# backend/app/stages/omr/oemer_adapter.py
"""L3 OMR 어댑터(1차): oemer로 이미지→MusicXML. OmrPort 구현."""
from __future__ import annotations
import subprocess
from pathlib import Path
from app.core.errors import OmrError

class OemerAdapter:
    def recognize(self, image_path: Path) -> Path:
        image_path = Path(image_path)
        if not image_path.exists():
            raise OmrError(f"이미지 없음: {image_path}")
        out_dir = image_path.parent
        proc = subprocess.run(
            ["oemer", str(image_path), "-o", str(out_dir)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise OmrError(f"oemer 실패(code={proc.returncode}): {proc.stderr[-500:]}")
        result = out_dir / f"{image_path.stem}.musicxml"
        if not result.exists():
            raise OmrError(f"MusicXML 미생성: {result}")
        return result
```

- [ ] **Step 5: 단위 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_oemer_adapter.py -v -m "not integration"`
Expected: PASS (missing-image 테스트). 통합 테스트는 `-m integration`으로 별도 수동 실행.

- [ ] **Step 6: Commit**

```bash
git add backend/app/stages/omr/oemer_adapter.py backend/app/core/errors.py backend/tests/test_oemer_adapter.py
git commit -m "feat(omr): oemer CLI adapter with OmrError surfacing"
```

---

## Task 6: 잡 상태 모델

**Files:**
- Modify: `backend/app/orchestration/job.py`
- Test: `backend/tests/test_job.py`

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_job.py
from app.orchestration.job import Job, JobStatus

def test_job_starts_queued():
    j = Job(id="abc")
    assert j.status == JobStatus.QUEUED

def test_fail_records_stage_and_reason():
    j = Job(id="abc")
    j.fail(JobStatus.OMR, "oemer crash")
    assert j.status == JobStatus.FAILED
    assert j.failed_stage == JobStatus.OMR
    assert "oemer" in j.error
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_job.py -v`
Expected: FAIL — import error

- [ ] **Step 3: 구현**

```python
# backend/app/orchestration/job.py
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
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_job.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestration/job.py backend/tests/test_job.py
git commit -m "feat(orchestration): job status model with failure capture"
```

---

## Task 7: Orchestrator — 1단계 파이프라인 (포트 의존, fake로 테스트)

**Files:**
- Modify: `backend/app/orchestration/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**설계:** 생성자 주입(OmrPort, ScoreParserPort, SvsPort, MixerPort). 4성부 합성은 `ThreadPoolExecutor`로 병렬(규칙: SVS만 병렬). 단계 실패는 `job.fail(stage, reason)`.

- [ ] **Step 1: 실패 테스트 (fake 어댑터)**

```python
# backend/tests/test_orchestrator.py
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_orchestrator.py -v`
Expected: FAIL — import error

- [ ] **Step 3: 구현**

```python
# backend/app/orchestration/orchestrator.py
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
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_orchestrator.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestration/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(orchestration): stage-1 pipeline with parallel SVS + failure capture"
```

---

## Task 8: Storage + FastAPI 엔드포인트

**Files:**
- Modify: `backend/app/storage/store.py`, `backend/app/api/schemas.py`, `backend/app/api/routes/jobs.py`, `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**설계:** 인메모리 잡 레지스트리(1단계 단순화) + `data/jobs/<id>/` 파일 저장. 업로드는 `POST /jobs`(BackgroundTasks로 오케스트레이터 실행), `GET /jobs/{id}`로 상태/결과 경로 조회. 보안: 파일명은 생성 UUID 디렉터리 + 고정명만 사용(traversal 차단) — 외부입력 경로이므로 security-reviewer 게이트 대상.

- [ ] **Step 1: 실패 테스트 (TestClient)**

```python
# backend/tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app

def test_create_and_get_job():
    client = TestClient(app)
    files = {"file": ("s.png", b"fakebytes", "image/png")}
    r = client.post("/jobs", files=files)
    assert r.status_code == 201
    job_id = r.json()["id"]
    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["status"] in {"queued","omr","parsing","synth","mixing","done","failed"}
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_api.py -v`
Expected: FAIL — import/route 없음

- [ ] **Step 3: store.py 구현**

```python
# backend/app/storage/store.py
"""L5 저장소: 업로드/결과/잡 메타. 1단계는 인메모리 레지스트리 + 파일."""
from __future__ import annotations
import uuid
from pathlib import Path
from app.orchestration.job import Job

DATA_ROOT = Path("data/jobs")

class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def new_job_dir(self) -> tuple[str, Path]:
        job_id = uuid.uuid4().hex
        d = DATA_ROOT / job_id
        d.mkdir(parents=True, exist_ok=True)
        return job_id, d

    def save(self, job: Job) -> None: self._jobs[job.id] = job
    def get(self, job_id: str) -> Job | None: return self._jobs.get(job_id)

store = JobStore()
```

- [ ] **Step 4: schemas.py 구현**

```python
# backend/app/api/schemas.py
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
```

- [ ] **Step 5: routes/jobs.py 구현**

```python
# backend/app/api/routes/jobs.py
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
    job = _orchestrator().run(job_id, image_path, work_dir)
    store.save(job)

@router.post("/jobs", response_model=JobCreated, status_code=201)
async def create_job(background: BackgroundTasks, file: UploadFile = File(...)) -> JobCreated:
    job_id, work_dir = store.new_job_dir()
    image_path = work_dir / "input.png"     # UUID 디렉터리 + 고정명 → traversal 차단
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
```

- [ ] **Step 6: main.py 구현**

```python
# backend/app/main.py
"""AIScore FastAPI 진입점 (L1)."""
from fastapi import FastAPI
from app.api.routes.jobs import router as jobs_router

app = FastAPI(title="AIScore")
app.include_router(jobs_router)
```

- [ ] **Step 7: 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest tests/test_api.py -v`
Expected: PASS (백그라운드 잡이 oemer를 호출하나, 테스트는 상태 조회만 검증)

- [ ] **Step 8: Commit**

```bash
git add backend/app/storage/store.py backend/app/api backend/app/main.py backend/tests/test_api.py
git commit -m "feat(api): job create/status endpoints + in-memory store"
```

---

## Task 9: 전체 단위 스위트 + 통합 스모크

**Files:**
- Test: 전체

- [ ] **Step 1: 전체 단위 통과 확인**

Run: `cd backend && PYTHONPATH=. pytest -v -m "not integration"`
Expected: 모든 단위 테스트 PASS

- [ ] **Step 2: (수동) 통합 스모크 — 실제 oemer e2e**

Run: `cd backend && PYTHONPATH=. pytest -v -m integration`
Expected: `온맘다해.png` → MusicXML 생성 PASS. **실패 시** 추측 수정 금지 → `superpowers:systematic-debugging`로 oemer 출력 분석 (가장 약한 고리, 설계 문서 §2 참조).

- [ ] **Step 3: (수동) 서버 기동 확인**

Run: `cd backend && PYTHONPATH=. uvicorn app.main:app --reload`
그리고 `curl -F file=@../score_images/온맘다해.png localhost:8000/jobs` → 반환된 id로 `GET /jobs/{id}` 폴링하여 `done` + `result_path`의 choir.wav 재생 확인.

- [ ] **Step 4: Commit (필요 시 픽스/문서)**

```bash
git commit -am "test: stage-1 integration smoke verified" --allow-empty
```

---

## Self-Review 체크 (계획 작성자 수행 완료)

- **스펙 커버리지:** 1단계 경로(OMR→파싱→SVS"우"→믹싱) 전 단계 + 잡/상태/API 포함. 가사/OCR/정렬/L4/training은 의도적으로 1단계 제외(`[2단계]`/트랙B).
- **Placeholder:** 모든 코드 스텝에 실제 코드 포함, TODO 없음.
- **타입 일관성:** `Note(pitch,quarter_length)`, `VoiceName`, `Job.fail(stage,reason)`, 포트 시그니처(`recognize/parse/synthesize/mix`)가 `ports.py`와 태스크 전반에서 일치.
- **미커버 리스크:** oemer 실제 인식 품질은 Task 9 통합 스모크에서만 검증됨(설계상 가장 약한 고리). 프론트엔드(OSMD)·교정 에디터·L4는 별도 계획.
