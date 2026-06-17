# Audiveris OMR 스테이지 구현 계획 (전처리 + 어댑터 + N성부 파서)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 저해상도 악보도 처리되도록 이미지 전처리(업스케일)를 추가하고, oemer 대신 **Audiveris**로 SATB 악보를 MusicXML로 인식하는 어댑터를 붙이며, 실제 OMR이 주는 **N성부(1~4)** 를 견고하게 파싱·합성한다.

**Architecture:** `OmrPort`(동결)에 `AudiverisAdapter` 추가(기존 코드 수정 아님, 규칙 7). 전처리는 OMR 직전 단계. 실측 결과 Audiveris는 SATB를 **2-part grand-staff(트레블 G + 베이스 F)** 로 인식하고 성부 분리는 빈약 → 파서는 `part×voice`를 **있는 만큼** S/A/T/B에 매핑하고, 오케스트레이터는 **존재하는 성부만** 합성한다. 완전한 4성부 분리는 교정 에디터/후속 과제.

**Tech Stack:** Python 3.10(conda `aiscore`), Pillow(업스케일), music21, **Audiveris 5.10.2**(소스 빌드, JDK 25 `openjdk@25`), pytest. Audiveris 배치: `bin/Audiveris -batch -transcribe -export -output <dir> <img>` → `.mxl`.

**검증 근거:** ROADMAP 2026-06-17 항목(저해상도가 근본원인; 3× 업스케일 시 Audiveris 성공: 2 part, clef G+F).

**전제(설치 완료됨):** `openjdk@25`(`/opt/homebrew/opt/openjdk@25`), Audiveris 빌드본(`/tmp/audiveris/app/build/distributions/app-5.10.2` — **휘발성, Task 1에서 안정 위치로 이전**), Tesseract 5.5.1.

**환경:** `conda activate` 대신 `/opt/miniconda3/envs/aiscore/bin/python`. 테스트: `cd backend && PYTHONPATH=. /opt/miniconda3/envs/aiscore/bin/python -m pytest ...`. 느린 Audiveris 테스트는 `@pytest.mark.integration`.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `vendor/audiveris/` (gitignore) | Audiveris 배포본 안정 위치(빌드 산출물, 비커밋) |
| `backend/app/core/config.py` | `audiveris_home`, `java_home`, `omr_min_long_edge` 설정(+env 오버라이드) |
| `backend/app/stages/omr/preprocess.py` | 업스케일/그레이스케일 전처리 |
| `backend/app/stages/omr/audiveris_adapter.py` | Audiveris 배치 CLI 래퍼 (OmrPort) — 기존 `audiveris_adapter.py` 스텁 대체 |
| `backend/app/stages/parsing/music21_parser.py` | (수정) `part×voice → S/A/T/B` 매핑, N성부 |
| `backend/app/orchestration/orchestrator.py` | (수정) 존재하는 성부만 합성 |
| `backend/tests/fixtures/satb_audiveris.mxl` | Audiveris 실출력 픽스처(파서 테스트용, 결정적) |
| `backend/tests/*` | 단위/통합 테스트 |

---

## Task 1: Audiveris 배포본 안정 위치 이전 + .gitignore

**Files:** Create `vendor/` (gitignore 추가). 빌드본 복사.

- [ ] **Step 1: 빌드본을 vendor로 복사**

Run:
```bash
cd /Users/sknoh/Documents/Workspace/aiscore
mkdir -p vendor/audiveris
cp -R /tmp/audiveris/app/build/distributions/app-5.10.2 vendor/audiveris/
ls vendor/audiveris/app-5.10.2/bin/Audiveris
```
Expected: `bin/Audiveris` 존재.

- [ ] **Step 2: .gitignore에 vendor 추가** (`# OS` 블록 위 또는 아래에)

```
# 빌드된 외부 엔진(대용량, 비커밋)
/vendor/
```

- [ ] **Step 3: 배치 동작 재확인(안정 경로)**

Run:
```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home
export TESSDATA_PREFIX=/opt/homebrew/share/tessdata
rm -rf /tmp/t1 && /Users/sknoh/Documents/Workspace/aiscore/vendor/audiveris/app-5.10.2/bin/Audiveris \
  -batch -transcribe -export -output /tmp/t1 /tmp/315_3x.png && ls /tmp/t1/*.mxl
```
Expected: `/tmp/t1/315_3x.mxl` 생성.

- [ ] **Step 4: Commit**

```bash
git add .gitignore && git commit -m "chore: vendor Audiveris dist (gitignored) + stable path"
```

---

## Task 2: Config — Audiveris/JDK 경로 + 전처리 파라미터

**Files:** Modify `backend/app/core/config.py`; Test `backend/tests/test_config.py`.

**설계:** 경로·파라미터를 한 곳에. env 오버라이드(이식성). 기본값은 검증된 로컬 경로.

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_config.py
import os
from app.core import config

def test_defaults_present():
    assert config.omr_min_long_edge() >= 1500
    assert "audiveris" in config.audiveris_bin().lower()

def test_env_override(monkeypatch):
    monkeypatch.setenv("AISCORE_OMR_MIN_LONG_EDGE", "1800")
    assert config.omr_min_long_edge() == 1800
```

- [ ] **Step 2: 실패 확인** — `cd backend && PYTHONPATH=. /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_config.py -v` → FAIL(import/attr).

- [ ] **Step 3: 구현** (`backend/app/core/config.py` 스텁 대체)

```python
"""횡단 설정: 경로·OMR 파라미터(pathlib 중립, env 오버라이드)."""
from __future__ import annotations
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]  # backend/app/core → repo root

def audiveris_home() -> Path:
    return Path(os.environ.get(
        "AISCORE_AUDIVERIS_HOME",
        str(_REPO / "vendor" / "audiveris" / "app-5.10.2")))

def audiveris_bin() -> str:
    return str(audiveris_home() / "bin" / "Audiveris")

def java_home() -> str | None:
    return os.environ.get(
        "AISCORE_JAVA_HOME",
        "/opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home")

def tessdata_prefix() -> str | None:
    return os.environ.get("AISCORE_TESSDATA_PREFIX", "/opt/homebrew/share/tessdata")

def omr_min_long_edge() -> int:
    return int(os.environ.get("AISCORE_OMR_MIN_LONG_EDGE", "2000"))
```

- [ ] **Step 4: 통과 확인** → PASS.

- [ ] **Step 5: Commit** — `git add backend/app/core/config.py backend/tests/test_config.py && git commit -m "feat(core): config for Audiveris/JDK paths + OMR params"`

---

## Task 3: 이미지 전처리 (업스케일/그레이스케일)

**Files:** Create `backend/app/stages/omr/preprocess.py`; Test `backend/tests/test_preprocess.py`.

**설계:** 긴 변이 `omr_min_long_edge` 미만이면 LANCZOS 업스케일(저해상도 = 모든 OMR 실패 근본원인). 그레이스케일 변환. 이미 충분하면 변환만.

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_preprocess.py
from PIL import Image
from app.stages.omr.preprocess import ensure_resolution

def _img(tmp_path, w, h):
    p = tmp_path / "in.png"; Image.new("RGB", (w, h), "white").save(p); return p

def test_upscales_small_image(tmp_path):
    src = _img(tmp_path, 500, 777)
    out = ensure_resolution(src, tmp_path / "out.png", min_long_edge=2000)
    w, h = Image.open(out).size
    assert max(w, h) >= 2000
    assert h > w  # 비율 유지

def test_keeps_large_image_dims(tmp_path):
    src = _img(tmp_path, 1600, 2400)
    out = ensure_resolution(src, tmp_path / "out.png", min_long_edge=2000)
    assert max(Image.open(out).size) == 2400
```

- [ ] **Step 2: 실패 확인** → FAIL.

- [ ] **Step 3: 구현**

```python
# backend/app/stages/omr/preprocess.py
"""OMR 전처리: 저해상도 업스케일 + 그레이스케일. (저해상도가 OMR 실패 근본원인)"""
from __future__ import annotations
from pathlib import Path
from PIL import Image

def ensure_resolution(src: Path, dst: Path, min_long_edge: int = 2000) -> Path:
    im = Image.open(src).convert("L")
    w, h = im.size
    long_edge = max(w, h)
    if long_edge < min_long_edge:
        scale = min_long_edge / long_edge
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    im.save(dst)
    return dst
```

- [ ] **Step 4: 통과 확인** → PASS.

- [ ] **Step 5: Commit** — `git add backend/app/stages/omr/preprocess.py backend/tests/test_preprocess.py && git commit -m "feat(omr): image preprocessing (upscale low-res before OMR)"`

---

## Task 4: AudiverisAdapter (배치 CLI 래퍼, OmrPort)

**Files:** Modify `backend/app/stages/omr/audiveris_adapter.py` (스텁 대체); Test `backend/tests/test_audiveris_adapter.py`.

**설계:** `recognize(image)` → 전처리 → Audiveris 배치 subprocess(JAVA_HOME/TESSDATA env) → 출력 `.mxl` 경로 반환. 실패(rc≠0 또는 .mxl 없음) → `OmrError`(조용한 실패 금지). 느린 실제 실행은 integration.

- [ ] **Step 1: 실패 테스트(단위 + 통합)**

```python
# backend/tests/test_audiveris_adapter.py
import pytest
from pathlib import Path
from app.stages.omr.audiveris_adapter import AudiverisAdapter
from app.core.errors import OmrError

def test_missing_image_raises(tmp_path):
    with pytest.raises(OmrError):
        AudiverisAdapter(work_dir=tmp_path).recognize(tmp_path / "nope.png")

@pytest.mark.integration
def test_recognize_315_produces_mxl(tmp_path):
    img = Path(__file__).parents[2] / "score_images" / "315.JPG"
    out = AudiverisAdapter(work_dir=tmp_path).recognize(img)
    assert out.exists() and out.suffix == ".mxl"
```

- [ ] **Step 2: 실패 확인(단위)** → `pytest tests/test_audiveris_adapter.py::test_missing_image_raises -v` FAIL.

- [ ] **Step 3: 구현**

```python
# backend/app/stages/omr/audiveris_adapter.py
"""L3 OMR 어댑터: Audiveris 배치 CLI로 이미지→MusicXML(.mxl). OmrPort 구현."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from app.core import config
from app.core.errors import OmrError
from app.stages.omr.preprocess import ensure_resolution

class AudiverisAdapter:
    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = Path(work_dir) if work_dir else Path("data/omr")

    def recognize(self, image_path: Path) -> Path:
        image_path = Path(image_path)
        if not image_path.exists():
            raise OmrError(f"이미지 없음: {image_path}")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        pre = ensure_resolution(image_path, self.work_dir / "pre.png",
                                config.omr_min_long_edge())
        env = dict(os.environ)
        if config.java_home():
            env["JAVA_HOME"] = config.java_home()
            env["PATH"] = f"{config.java_home()}/bin:" + env.get("PATH", "")
        if config.tessdata_prefix():
            env["TESSDATA_PREFIX"] = config.tessdata_prefix()
        bin_path = config.audiveris_bin()
        if not Path(bin_path).exists():
            raise OmrError(f"Audiveris 미설치: {bin_path}")
        proc = subprocess.run(
            [bin_path, "-batch", "-transcribe", "-export",
             "-output", str(self.work_dir), str(pre)],
            capture_output=True, text=True, env=env,
        )
        mxl = next(iter(self.work_dir.glob("*.mxl")), None)
        if proc.returncode != 0 or mxl is None:
            raise OmrError(
                f"Audiveris 실패(code={proc.returncode}, mxl={mxl}): "
                f"{proc.stderr[-500:]}")
        return mxl
```

- [ ] **Step 4: 단위 통과 확인** → `pytest tests/test_audiveris_adapter.py -v -m "not integration"` PASS(1).

- [ ] **Step 5: (수동) 통합** → `pytest tests/test_audiveris_adapter.py -v -m integration` (JAVA_HOME/TESSDATA 자동 주입, 느림). 실패 시 추측 금지 → systematic-debugging.

- [ ] **Step 6: Commit** — `git add backend/app/stages/omr/audiveris_adapter.py backend/tests/test_audiveris_adapter.py && git commit -m "feat(omr): Audiveris batch adapter with preprocessing + error surfacing"`

---

## Task 5: 파서 보강 — part×voice → S/A/T/B (N성부)

**Files:** Modify `backend/app/stages/parsing/music21_parser.py`; 픽스처 `backend/tests/fixtures/satb_audiveris.mxl`; Test `backend/tests/test_parser_satb.py`.

**설계(실측 기반):** Audiveris는 2-part(트레블 G + 베이스 F) 산출, 성부 분리 빈약. 매핑 규칙: 각 파트의 music21 Voice가 여러 개면 voice별로, 없으면 파트 전체를 한 라인으로. 라인들을 순서대로 S→A→T→B에 채우되(트레블 라인 먼저, 베이스 나중), **있는 만큼만**. 4 초과는 무시, 미만이면 그 성부 없음.

- [ ] **Step 1: 픽스처 커밋** — 실측 산출물을 픽스처로 복사.

```bash
cp /tmp/aud_out2/315_3x.mxl /Users/sknoh/Documents/Workspace/aiscore/backend/tests/fixtures/satb_audiveris.mxl
```

- [ ] **Step 2: 실패 테스트**

```python
# backend/tests/test_parser_satb.py
from pathlib import Path
from app.stages.parsing.music21_parser import Music21Parser
from app.domain.score import VoiceName

FIX = Path(__file__).parent / "fixtures" / "satb_audiveris.mxl"

def test_parses_at_least_two_voices_from_grandstaff():
    score = Music21Parser().parse(FIX)
    # 트레블+베이스 → 최소 2성부, 4 이하
    assert 2 <= len(score.voices) <= 4
    # 가장 위 성부는 소프라노 슬롯
    assert VoiceName.SOPRANO in score.voices
    assert len(score.voices[VoiceName.SOPRANO].notes) > 0
```

- [ ] **Step 3: 실패 확인** → 기존 파서는 4 Part 가정이라 2 Part에서 S만 채워 통과할 수도/아닐 수도. 먼저 실행해 실제 실패/통과를 확인하고, 통과하면 매핑이 빈약하므로 아래 구현으로 **명시적 라인 추출**로 교체.

- [ ] **Step 4: 구현** (parse 메서드 교체)

```python
# backend/app/stages/parsing/music21_parser.py
"""L3 파싱: MusicXML → 내부 Score. part×voice를 S/A/T/B에 있는 만큼 매핑."""
from __future__ import annotations
from pathlib import Path
from music21 import converter, stream, note as m21note
from app.domain.score import Score, Voice, Note, VoiceName

_ORDER = [VoiceName.SOPRANO, VoiceName.ALTO, VoiceName.TENOR, VoiceName.BASS]

def _notes_from(elements) -> list[Note]:
    out: list[Note] = []
    for el in elements:
        if isinstance(el, m21note.Rest):
            out.append(Note(pitch=None, quarter_length=float(el.duration.quarterLength)))
        elif isinstance(el, m21note.Note):
            out.append(Note(pitch=el.pitch.nameWithOctave,
                            quarter_length=float(el.duration.quarterLength)))
        elif hasattr(el, "pitches") and el.pitches:  # Chord → 최상단
            top = max(el.pitches, key=lambda p: p.midi)
            out.append(Note(pitch=top.nameWithOctave,
                            quarter_length=float(el.duration.quarterLength)))
    return out

class Music21Parser:
    def parse(self, musicxml_path: Path) -> Score:
        parsed = converter.parse(str(musicxml_path))
        lines: list[list[Note]] = []
        for part in parsed.getElementsByClass(stream.Part):
            voices = list(part.recurse().getElementsByClass(stream.Voice))
            if voices:
                for v in voices:
                    ns = _notes_from(v.notesAndRests)
                    if ns:
                        lines.append(ns)
            else:
                ns = _notes_from(part.recurse().notesAndRests)
                if ns:
                    lines.append(ns)
        voices_map: dict[VoiceName, Voice] = {}
        for vn, notes in zip(_ORDER, lines):  # 있는 만큼만
            voices_map[vn] = Voice(name=vn, notes=notes)
        return Score(voices=voices_map)
```

- [ ] **Step 5: 통과 확인** → `pytest tests/test_parser_satb.py tests/test_parser.py -v` 모두 PASS (기존 4-part 픽스처도 여전히 통과).

- [ ] **Step 6: Commit** — `git add backend/app/stages/parsing/music21_parser.py backend/tests/test_parser_satb.py backend/tests/fixtures/satb_audiveris.mxl && git commit -m "feat(parsing): map part×voice to SATB (N voices, real Audiveris output)"`

---

## Task 6: 오케스트레이터 — 존재하는 성부만 합성

**Files:** Modify `backend/app/orchestration/orchestrator.py`; Test `backend/tests/test_orchestrator_nvoice.py`.

**설계:** 현재 `for v in VoiceName`(4 고정) → `score.voices` 키만 순회. 없는 성부 KeyError 방지(리뷰 IMPORTANT).

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_orchestrator_nvoice.py
from pathlib import Path
import soundfile as sf, numpy as np
from app.domain.score import Score, Voice, Note, VoiceName
from app.orchestration.orchestrator import Stage1Orchestrator
from app.orchestration.job import JobStatus

class Omr:  # noqa
    def recognize(self, p): return Path("x.musicxml")
class Parser2:
    def parse(self, p):  # 2성부만
        return Score(voices={
            VoiceName.SOPRANO: Voice(VoiceName.SOPRANO, [Note("A4", 1.0)]),
            VoiceName.BASS: Voice(VoiceName.BASS, [Note("F3", 1.0)]),
        })
class Svs:
    def synthesize(self, score, voice, out):
        sf.write(out, np.zeros(100, dtype=np.float32), 44100); return out
class Mix:
    def mix(self, wavs, out):
        assert len(wavs) == 2  # 존재하는 2성부만
        sf.write(out, np.zeros(100, dtype=np.float32), 44100); return out

def test_synthesizes_only_present_voices(tmp_path):
    job = Stage1Orchestrator(Omr(), Parser2(), Svs(), Mix()).run("j", Path("x.png"), tmp_path)
    assert job.status == JobStatus.DONE
```

- [ ] **Step 2: 실패 확인** → 현재 4성부 고정이라 KeyError(ALTO) → FAIL.

- [ ] **Step 3: 구현** (synth 구간만 수정)

```python
            present = [v for v in VoiceName if v in score.voices]
            def synth(v: VoiceName) -> Path:
                return self.svs.synthesize(score, v, work_dir / f"{v.value}.wav")
            with ThreadPoolExecutor(max_workers=4) as ex:
                wavs = list(ex.map(synth, present))
```
(기존 `list(VoiceName)` → `present`로 교체. import 변경 없음.)

- [ ] **Step 4: 통과 확인** → `pytest tests/test_orchestrator_nvoice.py tests/test_orchestrator.py -v` 모두 PASS.

- [ ] **Step 5: Commit** — `git add backend/app/orchestration/orchestrator.py backend/tests/test_orchestrator_nvoice.py && git commit -m "feat(orchestration): synthesize only present voices (N-voice robust)"`

---

## Task 7: 전체 검증 + Audiveris 어댑터 배선(선택 토글)

**Files:** Modify `backend/app/api/routes/jobs.py`(어댑터 교체); Test: 전체.

- [ ] **Step 1: 라우트에서 OMR 어댑터를 Audiveris로 교체**

`_orchestrator()`의 `OemerAdapter()` → `AudiverisAdapter()` 로 변경(oemer 어댑터는 단성부용으로 보존).
```python
from app.stages.omr.audiveris_adapter import AudiverisAdapter
def _orchestrator() -> Stage1Orchestrator:
    return Stage1Orchestrator(AudiverisAdapter(), Music21Parser(), VowelSynthAdapter(), Mixer())
```

- [ ] **Step 2: 전체 단위 통과** → `cd backend && PYTHONPATH=. /opt/miniconda3/envs/aiscore/bin/python -m pytest -v -m "not integration"` 전부 PASS.

- [ ] **Step 3: (수동) E2E 통합** → 서버 기동 후 `315.JPG` 업로드 → 잡 `done` + choir.wav(2성부 "우") 생성/재생 확인. (JAVA_HOME 등은 config 기본값이 자동 주입)

- [ ] **Step 4: Commit** — `git add backend/app/api/routes/jobs.py && git commit -m "feat(api): wire Audiveris OMR adapter into stage-1 pipeline"`

---

## Self-Review 체크
- **스펙 커버리지:** 전처리(저해상도 근본원인) + Audiveris 어댑터(검증된 배치 CLI) + N성부 파서/오케스트레이터(실측 2-part 반영) + 배선. 모두 포함.
- **Placeholder:** 모든 코드 스텝에 실제 코드. TODO 없음.
- **타입 일관성:** `OmrPort.recognize(image)->Path`, `Note(pitch,quarter_length)`, `VoiceName`, `Score.voices` dict — 전 태스크 일치.
- **미커버/리스크:** ① Audiveris 4성부 완전분리는 안 됨(2성부 가이드가 현실) → 완전 SATB는 교정 에디터/후속. ② 배포본이 로컬 빌드(`vendor/`, 비커밋) → 이식 시 재빌드 필요(문서화). ③ JDK25/Tesseract 환경 의존(config로 분리).
