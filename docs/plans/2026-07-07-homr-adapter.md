# homr OMR 어댑터 구현 계획 (Audiveris → homr 최소 스위치)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 실행 중인 파이프라인의 OMR 엔진을 Audiveris에서 사전학습 homr로 전환하여, homr 출력으로 4성부(SATB) 가이드가 끝까지 나오게 한다.

**Architecture:** `HomrAdapter(OmrPort)`를 신규 추가(subprocess로 homr CLI 실행)하고, 배선(`jobs.py`)에서 주입 어댑터만 교체한다. 파서(`Music21Parser`)는 homr가 항상 파트명을 "Piano"로 내보내 악기 필터에 걸리는 문제만 폴백으로 해결한다. Audiveris 자산(어댑터·config·vendor·테스트)은 그대로 둔다. 오케스트레이터는 무수정.

**Tech Stack:** Python 3.10(conda aiscore), music21, subprocess, pytest. homr는 별도 clone(`../homr`)의 Python 3.11 venv + ONNX 모델을 subprocess로 호출.

## Global Constraints

- Python: conda `aiscore`(py3.10). 비대화형 셸에서 `conda activate` 실패 시 `/opt/miniconda3/envs/aiscore/bin/python` 절대경로 사용.
- `domain/`에 torch·fastapi·music21 import 금지(순수). 어댑터는 `stages/`에만.
- 새 외부 엔진 = 새 어댑터 파일(규칙 A7). 기존 Audiveris 코드 수정/삭제 금지(이번 스코프: 그대로 둠).
- 조용한 실패 금지(규칙 12): OMR 실패 = `OmrError` → 잡 `failed`(단계+원인).
- 외부 입력 경로: subprocess는 `shell=False`(리스트 인자)로 인젝션 차단(규칙 14).
- TDD(규칙 8): 구현 전 실패 테스트 먼저. 검증 없는 완료 금지(규칙 10).
- 응답·주석 한국어. 약어 첫 등장 시 풀네임 병기.
- 테스트 실행: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest ...` (integration 마크는 기본 제외됨).

**참고 사실(실측 완료):**
- homr CLI: `<homr>/.venv/bin/homr <image>` → 입력 옆에 `<stem>.musicxml` 생성. returncode·파일존재로 성공 판정.
- music21는 homr의 2-staff를 **2개 `PartStaff`(둘 다 name="Piano")**로 파싱. treble=S+A 화음, bass=T+B 화음. 기존 `_split_two_voices`가 PartStaff별로 그대로 동작.
- 현재 `_is_vocal_part("Piano")` → False → 두 성악 파트가 버려져 `ParseError`. ← 유일한 진짜 블로커.

---

## Task 1: config에 homr 실행 경로 추가

**Files:**
- Modify: `backend/app/core/config.py` (끝에 함수 추가)
- Test: `backend/tests/test_config.py` (케이스 추가)

**Interfaces:**
- Produces: `config.homr_bin() -> str` — homr 실행파일 절대경로. 기본 `<repo>/../homr/.venv/bin/homr`, env `AISCORE_HOMR_BIN` override.

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_config.py`에 추가

```python
def test_homr_bin_default_points_to_sibling_venv():
    from app.core import config
    b = config.homr_bin()
    assert b.endswith("homr/.venv/bin/homr")

def test_homr_bin_env_override(monkeypatch):
    from app.core import config
    monkeypatch.setenv("AISCORE_HOMR_BIN", "/custom/homr")
    assert config.homr_bin() == "/custom/homr"
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: module 'app.core.config' has no attribute 'homr_bin'`

- [ ] **Step 3: 최소 구현** — `backend/app/core/config.py` 끝에 추가

```python
def homr_bin() -> str:
    """homr CLI 실행파일 경로. 기본: 형제 clone의 venv 실행파일."""
    return os.environ.get(
        "AISCORE_HOMR_BIN",
        str(_REPO.parent / "homr" / ".venv" / "bin" / "homr"))
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (신규 2건 포함 전체 통과)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/core/config.py backend/tests/test_config.py
git commit -m "feat(omr): config.homr_bin() 추가 — homr CLI 경로(env override)"
```

---

## Task 2: HomrAdapter (OmrPort 구현)

**Files:**
- Create: `backend/app/stages/omr/homr_adapter.py`
- Test: `backend/tests/test_homr_adapter.py`

**Interfaces:**
- Consumes: `config.homr_bin()` (Task 1), `app.core.errors.OmrError`.
- Produces: `HomrAdapter(work_dir: Path | None = None)` with `recognize(image_path: Path) -> Path`. 입력 이미지를 `work_dir/omr/`에 복사 후 homr 실행, 생성된 `.musicxml` 경로 반환. 실패 시 `OmrError`.

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_homr_adapter.py` 신규

```python
from pathlib import Path
import pytest
from app.core.errors import OmrError
from app.stages.omr.homr_adapter import HomrAdapter


def test_missing_image_raises(tmp_path):
    with pytest.raises(OmrError):
        HomrAdapter(work_dir=tmp_path).recognize(tmp_path / "nope.png")


def test_homr_binary_missing_raises(tmp_path, monkeypatch):
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)  # 더미(존재만 확인)
    monkeypatch.setattr("app.stages.omr.homr_adapter.config.homr_bin",
                        lambda: str(tmp_path / "no_such_homr"))
    with pytest.raises(OmrError):
        HomrAdapter(work_dir=tmp_path).recognize(img)


def test_recognize_returns_musicxml_on_success(tmp_path, monkeypatch):
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    fake_bin = tmp_path / "homr"
    fake_bin.write_text("#!/bin/sh\n")  # 존재만 하면 됨(run은 모킹)

    monkeypatch.setattr("app.stages.omr.homr_adapter.config.homr_bin",
                        lambda: str(fake_bin))

    # subprocess.run 모킹: homr가 <stem>.musicxml을 만든 것처럼 흉내
    def fake_run(cmd, **kw):
        img_arg = Path(cmd[-1])
        img_arg.with_suffix(".musicxml").write_text("<score-partwise/>")
        class R: returncode = 0; stderr = ""
        return R()
    monkeypatch.setattr("app.stages.omr.homr_adapter.subprocess.run", fake_run)

    out = HomrAdapter(work_dir=tmp_path).recognize(img)
    assert out.exists() and out.suffix == ".musicxml"


def test_nonzero_returncode_raises(tmp_path, monkeypatch):
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    fake_bin = tmp_path / "homr"; fake_bin.write_text("#!/bin/sh\n")
    monkeypatch.setattr("app.stages.omr.homr_adapter.config.homr_bin",
                        lambda: str(fake_bin))
    def fake_run(cmd, **kw):
        class R: returncode = 1; stderr = "boom"
        return R()
    monkeypatch.setattr("app.stages.omr.homr_adapter.subprocess.run", fake_run)
    with pytest.raises(OmrError):
        HomrAdapter(work_dir=tmp_path).recognize(img)
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_homr_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: app.stages.omr.homr_adapter`

- [ ] **Step 3: 최소 구현** — `backend/app/stages/omr/homr_adapter.py` 신규

```python
"""L3 OMR 어댑터: homr CLI(subprocess)로 이미지→MusicXML. OmrPort 구현.

homr는 별도 clone의 Python 3.11 venv + ONNX 모델로 실행되므로 프로세스로 격리한다.
homr는 입력 이미지 옆에 <stem>.musicxml 을 생성한다.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from app.core import config
from app.core.errors import OmrError


class HomrAdapter:
    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = Path(work_dir) if work_dir else Path("data/omr")

    def recognize(self, image_path: Path) -> Path:
        image_path = Path(image_path)
        if not image_path.exists():
            raise OmrError(f"이미지 없음: {image_path}")

        bin_path = config.homr_bin()
        if not Path(bin_path).exists():
            raise OmrError(f"homr 미설치: {bin_path}")

        omr_dir = self.work_dir / "omr"
        omr_dir.mkdir(parents=True, exist_ok=True)
        # 입력을 잡 전용 디렉터리로 복사 → homr 출력을 여기로 유도(격리·결정적 경로)
        local_img = omr_dir / f"input{image_path.suffix or '.png'}"
        shutil.copyfile(image_path, local_img)

        proc = subprocess.run(
            [bin_path, str(local_img)],
            capture_output=True, text=True,  # shell=False (리스트 인자)
        )
        out = local_img.with_suffix(".musicxml")
        if proc.returncode != 0 or not out.exists():
            raise OmrError(
                f"homr 실패(code={proc.returncode}, xml_exists={out.exists()}): "
                f"{proc.stderr[-500:]}")
        return out
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_homr_adapter.py -v`
Expected: PASS (4건)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/stages/omr/homr_adapter.py backend/tests/test_homr_adapter.py
git commit -m "feat(omr): HomrAdapter(OmrPort) — subprocess homr CLI, 실패=OmrError"
```

---

## Task 3: HomrAdapter가 OmrPort 계약 만족 (포트 테스트)

**Files:**
- Modify: `backend/tests/test_ports.py` (케이스 추가)

**Interfaces:**
- Consumes: `HomrAdapter`(Task 2), `app.domain.ports.OmrPort`.

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_ports.py`에 추가

```python
def test_homr_adapter_satisfies_omr_port():
    from pathlib import Path
    from app.stages.omr.homr_adapter import HomrAdapter
    from app.domain.ports import OmrPort
    assert isinstance(HomrAdapter(work_dir=Path("/tmp")), OmrPort)
```

- [ ] **Step 2: 실패/통과 확인** (runtime_checkable Protocol이라 recognize만 있으면 통과)

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_ports.py -v`
Expected: PASS (신규 포함). 만약 FAIL이면 `recognize` 시그니처 확인.

- [ ] **Step 3: 커밋**

```bash
git add backend/tests/test_ports.py
git commit -m "test(omr): HomrAdapter OmrPort 계약 테스트"
```

---

## Task 4: 파서 — homr "Piano" 성악 파트 폴백

**Files:**
- Modify: `backend/app/stages/parsing/music21_parser.py`
- Test: `backend/tests/test_parser_homr.py` (신규)
- Fixture: `backend/tests/fixtures/satb_homr.musicxml` (실제 homr 출력 복사)

**Interfaces:**
- Produces: `Music21Parser().parse(path)` — 모든 파트가 악기명("Piano")이어도, 엄격 필터가 0줄이면 필터를 해제하고 재추출하여 SATB `Score` 반환.

- [ ] **Step 1: 픽스처 준비** (실제 homr 출력 1곡 복사)

```bash
cp training/baseline_eval/homr_full/hymn001_Normal.musicxml \
   backend/tests/fixtures/satb_homr.musicxml
```

- [ ] **Step 2: 실패 테스트 작성** — `backend/tests/test_parser_homr.py` 신규

```python
from pathlib import Path
from app.stages.parsing.music21_parser import Music21Parser
from app.domain.score import VoiceName

FIX = Path(__file__).parent / "fixtures" / "satb_homr.musicxml"


def test_homr_piano_part_yields_satb():
    """homr는 파트명을 'Piano'로 내보내지만 성악 내용이다. 4성부가 나와야 한다."""
    score = Music21Parser().parse(FIX)
    # treble(S+A) + bass(T+B) 화음 분리 → 최소 소프라노·베이스는 존재
    assert VoiceName.SOPRANO in score.voices
    assert VoiceName.BASS in score.voices
    assert len(score.voices[VoiceName.SOPRANO].notes) > 0
```

- [ ] **Step 3: 실패 확인**

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_parser_homr.py -v`
Expected: FAIL — `ParseError: 파싱 결과 음표 없음` (Piano 필터가 두 파트를 버림)

- [ ] **Step 4: 구현** — `music21_parser.py` 리팩터: 추출 루프를 헬퍼로 분리하고 폴백 추가

`parse` 메서드(라인 63~98)를 아래로 교체:

```python
    def parse(self, musicxml_path: Path) -> Score:
        parsed = converter.parse(str(musicxml_path))
        parts = list(parsed.getElementsByClass(stream.Part))

        # 1차: 악기 파트 제외(Audiveris 반주 배제용)
        lines = self._extract_lines(parts, vocal_only=True)
        if not lines:
            # 모든 파트가 악기명이지만 실제 성악 내용인 경우
            # (homr는 항상 파트명을 "Piano"로 내보냄) → 필터 해제 재추출
            _logger.info("성악 파트 필터 결과 0줄 → 악기 필터 해제 폴백")
            lines = self._extract_lines(parts, vocal_only=False)

        if not lines:
            raise ParseError(f"파싱 결과 음표 없음: {musicxml_path}")

        voices_map: dict[VoiceName, Voice] = {}
        for vn, notes in zip(_ORDER, lines):
            voices_map[vn] = Voice(name=vn, notes=notes)
        return Score(voices=voices_map)

    def _extract_lines(self, parts, vocal_only: bool) -> list[list[Note]]:
        lines: list[list[Note]] = []
        for part in parts:
            if vocal_only and not _is_vocal_part(part):
                continue
            elements = list(part.recurse().notesAndRests)
            has_chord = any(hasattr(e, "pitches") and len(e.pitches) >= 2
                            for e in elements)
            if has_chord:
                upper, lower = _split_two_voices(elements)
                if upper:
                    lines.append(upper)
                if lower:
                    lines.append(lower)
            else:
                ns: list[Note] = []
                for el in elements:
                    dur = float(el.duration.quarterLength)
                    if isinstance(el, m21note.Rest):
                        ns.append(Note(pitch=None, quarter_length=dur))
                    elif isinstance(el, m21note.Note):
                        ns.append(Note(pitch=el.pitch.nameWithOctave,
                                       quarter_length=dur))
                if ns:
                    lines.append(ns)
        return lines
```

또한 파일 상단 docstring(라인 3~5)에 homr 구조를 한 줄 추가:

```python
"""L3 파싱: MusicXML → 내부 Score.

Audiveris 출력 구조:
  - Grand staff 2-Part: Part0(G clef)=S+A 화음, Part1(F clef)=T+B 화음
  - 화음 상단 → 위 성부(S/T), 하단 → 아래 성부(A/B) 로 분리
homr 출력 구조:
  - 단일 "Piano" 파트가 music21에서 2개 PartStaff(treble/bass)로 파싱됨.
  - 파트명이 "Piano"라 악기 필터에 걸리므로, 필터 결과가 0줄이면 필터를 해제(폴백).

악기 필터: 파트명에 악기 키워드(Piano, Organ 등)가 있으면 제외.
파트명 없으면 성악으로 간주(폴백).
"""
```

- [ ] **Step 5: 통과 확인 + Audiveris 파서 회귀**

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_parser_homr.py tests/test_parser_satb.py -v`
Expected: PASS (homr 신규 + 기존 Audiveris 픽스처 회귀 모두 통과)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/stages/parsing/music21_parser.py backend/tests/test_parser_homr.py backend/tests/fixtures/satb_homr.musicxml
git commit -m "feat(parsing): homr 'Piano' 성악 파트 폴백 — 필터 0줄시 해제 재추출"
```

---

## Task 5: 배선 교체 — jobs.py가 HomrAdapter 주입

**Files:**
- Modify: `backend/app/api/routes/jobs.py:15,26-28`
- Test: `backend/tests/test_jobs_wiring.py` (신규)

**Interfaces:**
- Consumes: `HomrAdapter`(Task 2). 오케스트레이터 생성 시 OMR 어댑터로 주입.

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_jobs_wiring.py` 신규

```python
import inspect
from app.api.routes import jobs


def test_run_uses_homr_adapter():
    """배선(_run)이 HomrAdapter를 사용해야 한다(Audiveris 아님)."""
    src = inspect.getsource(jobs._run)
    assert "HomrAdapter" in src
    assert "AudiverisAdapter" not in src
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_jobs_wiring.py -v`
Expected: FAIL — `assert "HomrAdapter" in src`

- [ ] **Step 3: 구현** — `jobs.py` import·주입 교체

라인 15 교체:
```python
from app.stages.omr.homr_adapter import HomrAdapter
```

라인 26~28의 `_run` 내부 오케스트레이터 생성 교체:
```python
    orch = Stage1Orchestrator(
        HomrAdapter(work_dir=work_dir),
        Music21Parser(), VowelSynthAdapter(), Mixer())
```

- [ ] **Step 4: 통과 확인 + 전체 회귀**

Run: `cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest -v`
Expected: PASS (전체 단위 테스트. integration 마크 제외됨)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/api/routes/jobs.py backend/tests/test_jobs_wiring.py
git commit -m "feat(api): 파이프라인 OMR 엔진 Audiveris→homr 전환(배선 교체)"
```

---

## Task 6: End-to-End 검증 (실제 homr 실행)

**Files:** 없음(검증만). 산출물은 커밋하지 않음(규칙 13).

- [ ] **Step 1: 실제 이미지 1장으로 파이프라인 수동 실행**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python - <<'PY'
from pathlib import Path
from app.stages.omr.homr_adapter import HomrAdapter
from app.stages.parsing.music21_parser import Music21Parser
img = Path("../training/baseline_eval/homr_full/hymn001_Normal.png")  # 실제 악보 이미지
work = Path("/tmp/homr_e2e"); work.mkdir(exist_ok=True)
xml = HomrAdapter(work_dir=work).recognize(img)
score = Music21Parser().parse(xml)
print("성부:", {v.value: len(sc.notes) for v, sc in score.voices.items()})
PY
```

Expected: `성부: {'soprano': N>0, 'alto': ..., 'tenor': ..., 'bass': N>0}` — 4성부(또는 최소 S/B) 채워짐. homr 실행에 수~수십초 소요.

- [ ] **Step 2: 결과 기록** — 성부별 음표 수를 확인. 크래시 시 `OmrError` 메시지 확인(정상 표면화).

- [ ] **Step 3: ROADMAP 갱신 + 커밋**

`docs/ROADMAP.md`의 OMR 경로 #3을 완료로 표시, 진행 이력에 날짜 항목 추가.

```bash
git add docs/ROADMAP.md
git commit -m "docs(omr): homr 어댑터 전환 완료 — 파이프라인 OMR 엔진 교체"
```

---

## Self-Review (작성자 체크)

**Spec 커버리지:**
- Stage A(HomrAdapter subprocess/OmrError) → Task 1,2,3 ✅
- Stage B(파서 homr 구조) → Task 4 ✅ (music21가 2 PartStaff로 주므로 스태프 분리 불필요, 필터 폴백만)
- 배선 교체 → Task 5 ✅
- E2E 검증 → Task 6 ✅
- Stage C/D/E(측정확장·후처리·파인튜닝) → 스펙에서 범위 밖(후속) ✅

**플레이스홀더:** 없음(모든 스텝에 실제 코드/명령).

**타입 일관성:** `HomrAdapter(work_dir=...)` / `recognize(image_path)->Path` / `config.homr_bin()->str` / `_extract_lines(parts, vocal_only)->list[list[Note]]` — 전 태스크 일치.

**리스크 메모:** Task 6에서 실제 homr가 hymn001.png에 대해 크래시하면(예: 저해상도) OmrError로 표면화됨 — 정상. 다른 이미지로 재시도.
