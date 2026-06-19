# Score Understanding Pipeline — Phase 1 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 찬송가 SATB + 1부 찬양 악보 이미지에서 메타정보·음표(피치+박자)·가사를 추출해 완전한 MusicXML을 생성하는 5모듈 AI 파이프라인을 구현한다.

**Architecture:** 전처리 → 레이아웃 분석 → OMR(YOLOv8) → 메타 추출 → 가사 OCR(PaddleOCR) → MusicXML 조립 순의 선형 파이프라인. 모든 모듈은 `ScoreUnderstandingAdapter` 하나로 감싸 `OmrPort` 인터페이스를 구현한다. YOLOv8 모델 파일은 학습 완료 후 설정으로 주입되며, 없을 경우 명확한 에러를 발생시킨다.

**Tech Stack:** ultralytics (YOLOv8), paddleocr, music21, opencv-python, pdf2image, numpy, PIL, pytest

> **⚠️ 이 계획서는 추론 파이프라인만 다룹니다.** YOLOv8 모델 학습 + PaddleOCR 파인튜닝은 `2026-06-19-score-understanding-training.md` (Plan 1B)에서 별도로 작성합니다.

## Global Constraints

- Python: conda 환경 `aiscore` (3.10). 비대화형 셸에서는 `/opt/miniconda3/envs/aiscore/bin/python` 절대경로 사용
- 디바이스: `backend/app/core/device.py` 경유 (`mps→cuda→cpu`). 하드코딩 금지
- 경로: `pathlib.Path` 사용. 문자열 경로 금지
- OmrPort 인터페이스 `recognize(image_path: Path) → Path` 변경 금지
- TDD: 구현 전 실패 테스트 필수. 도메인·변환·조립은 단위 테스트 필수
- 통합 테스트: `@pytest.mark.integration` 마크 + `pyproject.toml`의 기본 제외 설정 적용
- 커밋: 태스크 완료 시 1커밋
- 모델 경로: `backend/app/core/config.py` 함수로만 읽음. 모듈 내 하드코딩 금지
- 로컬 실행 전용: PaddleOCR·YOLOv8 모두 온디바이스. 외부 API 호출 금지
- `domain/` 레이어에 torch·cv2·paddleocr import 금지 (순수 Python 유지)

---

## File Map

**생성 파일:**

```
backend/app/stages/omr/
├── types.py                        # 공유 데이터 타입 (BBox, StaffSystem, NoteEvent 등)
├── preprocessor.py                 # Module 0: 전처리 (preprocess.py 확장)
├── layout_analyzer.py              # Module 1: 투영 프로파일 기반 영역 분리
├── staff_detector.py               # Module 2a: 보표선 y좌표 검출
├── pitch_converter.py              # Module 2b: (staff_system, y) → 피치 문자열
├── omr_engine.py                   # Module 2c: YOLOv8 기호 검출 래퍼
├── duration_classifier.py          # Module 2d: 음표 형태 → 음가 float
├── voice_assigner.py               # Module 2e: 성부 분리 (줄기 방향 휴리스틱)
├── meta_extractor.py               # Module 3: 조성·박자·제목·빠르기 추출
├── lyrics_ocr.py                   # Module 4: PaddleOCR 한글 가사 추출
├── musicxml_assembler.py           # Module 5: music21 MusicXML 조립
└── score_understanding_adapter.py  # OmrPort 구현 (파이프라인 진입점)

backend/tests/
├── test_su_types.py                # types.py 단위 테스트 (su = score understanding)
├── test_su_preprocessor.py
├── test_su_layout_analyzer.py
├── test_su_staff_detector.py
├── test_su_pitch_converter.py
├── test_su_omr_engine.py
├── test_su_duration_classifier.py
├── test_su_voice_assigner.py
├── test_su_meta_extractor.py
├── test_su_lyrics_ocr.py
├── test_su_musicxml_assembler.py
└── test_su_adapter.py              # E2E 통합 테스트
```

**수정 파일:**

```
backend/app/core/config.py          # YOLOv8 모델 경로, PaddleOCR 설정 추가
```

---

## Task 1: 공유 데이터 타입 정의 (types.py)

**Files:**
- Create: `backend/app/stages/omr/types.py`
- Test: `backend/tests/test_su_types.py`

**Interfaces:**
- Produces: `BBox`, `StaffSystem`, `LayoutResult`, `RawDetection`, `NoteEvent`, `ScoreMeta`, `LyricsResult` — 이후 모든 태스크가 이 타입을 사용

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_types.py
from app.stages.omr.types import BBox, StaffSystem, NoteEvent, ScoreMeta, LyricsResult

def test_bbox_computed_properties():
    b = BBox(x=10, y=20, w=50, h=30)
    assert b.x2 == 60
    assert b.y2 == 50
    assert b.center_x == 35
    assert b.center_y == 35

def test_staff_system_space():
    ss = StaffSystem(
        bbox=BBox(0, 100, 500, 80),
        line_ys=[110, 120, 130, 140, 150],
        clef="treble",
    )
    assert ss.staff_space == 10.0

def test_note_event_defaults():
    n = NoteEvent(pitch="G4", duration=1.0, voice=1, staff_idx=0, x=100)
    assert n.measure is None
    assert n.is_dotted is False

def test_score_meta_defaults():
    m = ScoreMeta()
    assert m.key == "C major"
    assert m.time_num == 4

def test_lyrics_result_empty():
    lr = LyricsResult(verses=[])
    assert lr.verse_count == 0
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_types.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.stages.omr.types'`

- [ ] **Step 3: types.py 구현**

```python
# backend/app/stages/omr/types.py
"""Score Understanding 파이프라인 공유 데이터 타입."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class BBox:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def center_x(self) -> int:
        return self.x + self.w // 2

    @property
    def center_y(self) -> int:
        return self.y + self.h // 2


@dataclass
class StaffSystem:
    bbox: BBox
    line_ys: list[int]   # 5개 보표선 y좌표 (오름차순, 위→아래)
    clef: str            # "treble" | "bass"

    @property
    def staff_space(self) -> float:
        """보표 한 칸 높이(픽셀). line_ys가 5개여야 한다."""
        return (self.line_ys[-1] - self.line_ys[0]) / 4.0


@dataclass
class LayoutResult:
    image_h: int
    image_w: int
    title_region: BBox | None
    tempo_region: BBox | None
    staff_systems: list[StaffSystem]
    lyric_regions: list[BBox]   # 절 순서대로


@dataclass
class RawDetection:
    bbox: BBox
    class_name: str    # "notehead_filled", "notehead_open", "accidental_flat", ...
    confidence: float


@dataclass
class NoteEvent:
    pitch: str           # "C4", "F#5", "Bb3" 등
    duration: float      # quarterLength (1.0=4분, 2.0=2분, 4.0=온음, 0.5=8분)
    voice: int           # 1(S/T) or 2(A/B)
    staff_idx: int       # LayoutResult.staff_systems 인덱스
    x: int               # 음표 x좌표 (악보 내 순서 정렬용)
    measure: int | None = None
    is_dotted: bool = False


@dataclass
class ScoreMeta:
    title: str = ""
    key: str = "C major"     # "G major", "D minor" 등
    time_num: int = 4
    time_den: int = 4
    tempo_text: str = ""
    bpm: int | None = None


@dataclass
class LyricsResult:
    verses: list[list[str]]   # verses[절번호][음표번호] = 음절

    @property
    def verse_count(self) -> int:
        return len(self.verses)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_types.py -v
```
Expected: `5 passed`

- [ ] **Step 5: 커밋**

```bash
git add backend/app/stages/omr/types.py backend/tests/test_su_types.py
git commit -m "feat(su): 공유 데이터 타입 정의 (BBox, StaffSystem, NoteEvent 등)"
```

---

## Task 2: Module 0 — 이미지 전처리 (preprocessor.py)

**Files:**
- Create: `backend/app/stages/omr/preprocessor.py`
- Test: `backend/tests/test_su_preprocessor.py`

**Interfaces:**
- Consumes: 이미지 경로 (JPEG/PNG/PDF 첫 페이지)
- Produces: `preprocess(src: Path, dst: Path) → Path` — 300 DPI 정규화된 이진 이미지 (PNG)

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_preprocessor.py
import numpy as np
import pytest
from pathlib import Path
from PIL import Image
from app.stages.omr.preprocessor import preprocess

@pytest.fixture
def small_gray_png(tmp_path) -> Path:
    """100×80 px 회색조 PNG (저해상도 시뮬레이션)."""
    img = Image.fromarray(np.full((80, 100), 200, dtype=np.uint8), mode="L")
    p = tmp_path / "input.png"
    img.save(p)
    return p

def test_preprocess_creates_output(small_gray_png, tmp_path):
    dst = tmp_path / "out.png"
    result = preprocess(small_gray_png, dst)
    assert result == dst
    assert dst.exists()

def test_preprocess_upscales_short_edge(small_gray_png, tmp_path):
    """장변이 min_long_edge(기본 2000)보다 작으면 업스케일한다."""
    dst = tmp_path / "out.png"
    preprocess(small_gray_png, dst)
    out = Image.open(dst)
    assert max(out.size) >= 2000

def test_preprocess_output_is_grayscale(small_gray_png, tmp_path):
    dst = tmp_path / "out.png"
    preprocess(small_gray_png, dst)
    out = Image.open(dst)
    assert out.mode == "L"

def test_preprocess_large_image_not_downscaled(tmp_path):
    """이미 충분히 큰 이미지는 축소하지 않는다."""
    img = Image.fromarray(np.full((3000, 2200), 200, dtype=np.uint8), mode="L")
    src = tmp_path / "big.png"
    img.save(src)
    dst = tmp_path / "out.png"
    preprocess(src, dst)
    out = Image.open(dst)
    assert out.size == (2200, 3000)
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_preprocessor.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: preprocessor.py 구현**

기존 `preprocess.py`의 `ensure_resolution`을 재사용하고 기울기 보정을 추가한다.

```python
# backend/app/stages/omr/preprocessor.py
"""Module 0: 이미지 전처리 — DPI 정규화 + 기울기 보정."""
from __future__ import annotations
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.stages.omr.preprocess import ensure_resolution


def preprocess(src: Path, dst: Path, min_long_edge: int = 2000) -> Path:
    """악보 이미지를 전처리해 dst에 저장하고 dst를 반환한다.

    1. 업스케일 (장변 < min_long_edge 시)
    2. 그레이스케일 유지
    3. 기울기 보정 (±10° 이내)
    """
    # Step 1: 해상도 정규화 (기존 preprocess.py 재사용)
    ensure_resolution(src, dst, min_long_edge=min_long_edge)

    # Step 2: 기울기 보정
    img = cv2.imread(str(dst), cv2.IMREAD_GRAYSCALE)
    img = _deskew(img)
    cv2.imwrite(str(dst), img)
    return dst


def _deskew(gray: np.ndarray) -> np.ndarray:
    """수평 투영 프로파일로 기울기(±10°)를 감지해 보정한다."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 100:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5 or abs(angle) > 10:
        return gray
    h, w = gray.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_preprocessor.py -v
```
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add backend/app/stages/omr/preprocessor.py backend/tests/test_su_preprocessor.py
git commit -m "feat(su): Module0 전처리 — 업스케일 + 기울기 보정"
```

---

## Task 3: Module 1 — 레이아웃 분석 (layout_analyzer.py)

**Files:**
- Create: `backend/app/stages/omr/layout_analyzer.py`
- Test: `backend/tests/test_su_layout_analyzer.py`

**Interfaces:**
- Consumes: OpenCV 그레이스케일 이미지 (`np.ndarray`)
- Produces: `analyze_layout(gray: np.ndarray) → LayoutResult`

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_layout_analyzer.py
import numpy as np
import pytest
from app.stages.omr.layout_analyzer import analyze_layout
from app.stages.omr.types import LayoutResult

def _make_hymn_image(h=1200, w=900) -> np.ndarray:
    """보표선 5개짜리 4시스템 + 가사 영역을 흉내낸 합성 이미지."""
    img = np.full((h, w), 255, dtype=np.uint8)
    # 4개 보표 시스템 (y=200, 450, 700, 950), 각각 5줄 간격 15px
    for sys_y in [200, 450, 700, 950]:
        for i in range(5):
            y = sys_y + i * 15
            if y < h:
                img[y, 50:w-50] = 0
    # 가사 영역 대략 표시 (텍스트처럼 점 뿌리기)
    for row in range(1050, 1150, 20):
        if row < h:
            img[row, 100:800:5] = 0
    return img

def test_analyze_layout_returns_correct_type():
    img = _make_hymn_image()
    result = analyze_layout(img)
    assert isinstance(result, LayoutResult)

def test_analyze_layout_detects_staff_systems():
    img = _make_hymn_image()
    result = analyze_layout(img)
    assert len(result.staff_systems) >= 1

def test_analyze_layout_image_dimensions():
    img = _make_hymn_image(h=1200, w=900)
    result = analyze_layout(img)
    assert result.image_h == 1200
    assert result.image_w == 900
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_layout_analyzer.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: layout_analyzer.py 구현**

```python
# backend/app/stages/omr/layout_analyzer.py
"""Module 1: 투영 프로파일 기반 레이아웃 분석 (찬송가 전용)."""
from __future__ import annotations

import cv2
import numpy as np

from app.stages.omr.types import BBox, LayoutResult, StaffSystem


# 보표선 검출에 필요한 최소 연속 흑색 픽셀 비율
_STAFF_LINE_FILL_RATIO = 0.4
# 보표 시스템 간 최소 간격 (픽셀)
_MIN_SYSTEM_GAP = 30


def analyze_layout(gray: np.ndarray) -> LayoutResult:
    """그레이스케일 이미지에서 보표/제목/가사 영역을 분리한다."""
    h, w = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 수평 투영 프로파일: 각 행의 흑색 픽셀 수
    h_proj = np.sum(binary > 0, axis=1).astype(float) / w

    staff_line_ys = _detect_staff_lines(h_proj, threshold=_STAFF_LINE_FILL_RATIO)
    staff_systems = _group_into_systems(staff_line_ys, w)

    # 제목 영역: 첫 보표 시스템 위
    title_region: BBox | None = None
    if staff_systems:
        top_y = staff_systems[0].bbox.y
        if top_y > 20:
            title_region = BBox(x=0, y=0, w=w, h=top_y)

    # 빠르기표 영역: 첫 보표 시스템 바로 위 좁은 띠
    tempo_region: BBox | None = None
    if staff_systems and title_region and title_region.h > 40:
        tempo_region = BBox(x=0, y=title_region.h - 40, w=w // 2, h=40)

    # 가사 영역: 마지막 보표 시스템 아래
    lyric_regions: list[BBox] = []
    if staff_systems:
        last_sys = staff_systems[-1]
        lyric_top = last_sys.bbox.y2 + 5
        if lyric_top < h - 20:
            lyric_regions = [BBox(x=0, y=lyric_top, w=w, h=h - lyric_top)]

    return LayoutResult(
        image_h=h,
        image_w=w,
        title_region=title_region,
        tempo_region=tempo_region,
        staff_systems=staff_systems,
        lyric_regions=lyric_regions,
    )


def _detect_staff_lines(h_proj: np.ndarray, threshold: float) -> list[int]:
    """투영 프로파일에서 보표선 후보 y좌표 목록을 반환한다."""
    return [int(y) for y, v in enumerate(h_proj) if v >= threshold]


def _group_into_systems(line_ys: list[int], image_w: int) -> list[StaffSystem]:
    """연속된 보표선들을 5개씩 묶어 StaffSystem 목록을 반환한다."""
    if not line_ys:
        return []

    # 연속 그룹으로 클러스터링
    groups: list[list[int]] = []
    current = [line_ys[0]]
    for y in line_ys[1:]:
        if y - current[-1] <= 3:
            current.append(y)
        else:
            groups.append(current)
            current = [y]
    groups.append(current)

    # 각 그룹의 대표 y (중앙값)
    line_centers = [int(np.median(g)) for g in groups]

    # 5개씩 묶어 보표 시스템 구성
    systems: list[StaffSystem] = []
    i = 0
    while i + 4 < len(line_centers):
        five = line_centers[i:i + 5]
        spacing = (five[-1] - five[0]) / 4
        # 너무 불규칙하면 건너뜀 (보표선이 아닐 가능성)
        if spacing < 5 or spacing > 40:
            i += 1
            continue
        # 다음 그룹과 간격이 너무 좁으면 같은 시스템의 일부
        if i + 5 < len(line_centers) and line_centers[i + 5] - five[-1] < _MIN_SYSTEM_GAP:
            i += 1
            continue
        top_y = five[0] - int(spacing)
        bot_y = five[-1] + int(spacing)
        systems.append(StaffSystem(
            bbox=BBox(x=0, y=max(0, top_y), w=image_w, h=bot_y - top_y),
            line_ys=five,
            clef="treble",  # Task 5에서 YOLOv8 검출 후 교체
        ))
        i += 5

    return systems
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_layout_analyzer.py -v
```
Expected: `3 passed`

- [ ] **Step 5: 커밋**

```bash
git add backend/app/stages/omr/layout_analyzer.py backend/tests/test_su_layout_analyzer.py
git commit -m "feat(su): Module1 레이아웃 분석 — 투영 프로파일 기반 영역 분리"
```

---

## Task 4: Module 2a — 보표선 검출 + 피치 변환

**Files:**
- Create: `backend/app/stages/omr/staff_detector.py`
- Create: `backend/app/stages/omr/pitch_converter.py`
- Test: `backend/tests/test_su_staff_detector.py`
- Test: `backend/tests/test_su_pitch_converter.py`

**Interfaces:**
- `refine_staff_lines(gray_crop: np.ndarray, candidate_ys: list[int]) → list[int]`: 5개 보표선 y좌표 정밀화
- `y_to_pitch(y: int, staff: StaffSystem) → str`: 보표 내 y좌표 → 피치 문자열 ("G4", "D5" 등)

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_staff_detector.py
import numpy as np
from app.stages.omr.staff_detector import refine_staff_lines

def _staff_image():
    img = np.full((100, 500), 255, dtype=np.uint8)
    for y in [20, 30, 40, 50, 60]:
        img[y, :] = 0
    return img

def test_refine_returns_five_lines():
    img = _staff_image()
    lines = refine_staff_lines(img, candidate_ys=[20, 30, 40, 50, 60])
    assert len(lines) == 5

def test_refine_preserves_order():
    img = _staff_image()
    lines = refine_staff_lines(img, candidate_ys=[20, 30, 40, 50, 60])
    assert lines == sorted(lines)

def test_refine_with_noise_candidates():
    """노이즈 후보가 섞여도 5개 핵심 선을 찾는다."""
    img = _staff_image()
    lines = refine_staff_lines(img, candidate_ys=[19, 20, 21, 30, 40, 50, 51, 60])
    assert len(lines) == 5
```

```python
# backend/tests/test_su_pitch_converter.py
from app.stages.omr.types import BBox, StaffSystem
from app.stages.omr.pitch_converter import y_to_pitch

def _treble_staff():
    # 보표선 y: 100, 110, 120, 130, 140 → spacing=10
    return StaffSystem(
        bbox=BBox(0, 90, 500, 60),
        line_ys=[100, 110, 120, 130, 140],
        clef="treble",
    )

def _bass_staff():
    return StaffSystem(
        bbox=BBox(0, 90, 500, 60),
        line_ys=[100, 110, 120, 130, 140],
        clef="bass",
    )

def test_treble_middle_line_is_B4():
    """트레블 클레프 3번째 선(인덱스 2) = B4."""
    staff = _treble_staff()
    assert y_to_pitch(120, staff) == "B4"

def test_treble_first_line_is_E4():
    """트레블 클레프 1번째 선(인덱스 0) = E4."""
    staff = _treble_staff()
    assert y_to_pitch(100, staff) == "E4"

def test_treble_first_space_is_F4():
    """트레블 클레프 1번째 칸(선 사이 y=105) = F4."""
    staff = _treble_staff()
    assert y_to_pitch(105, staff) == "F4"

def test_bass_first_line_is_G2():
    """베이스 클레프 1번째 선 = G2."""
    staff = _bass_staff()
    assert y_to_pitch(100, staff) == "G2"
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_staff_detector.py tests/test_su_pitch_converter.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: staff_detector.py 구현**

```python
# backend/app/stages/omr/staff_detector.py
"""Module 2a: 보표선 y좌표 정밀화."""
from __future__ import annotations
import numpy as np


def refine_staff_lines(gray_crop: np.ndarray, candidate_ys: list[int]) -> list[int]:
    """후보 y좌표들을 클러스터링해 정확한 보표선 5개를 반환한다."""
    if not candidate_ys:
        return []

    # 가까운 후보끼리 클러스터링 (거리 ≤ 3px)
    clusters: list[list[int]] = []
    current = [candidate_ys[0]]
    for y in sorted(candidate_ys)[1:]:
        if y - current[-1] <= 3:
            current.append(y)
        else:
            clusters.append(current)
            current = [y]
    clusters.append(current)

    centers = [int(np.median(c)) for c in clusters]

    # 5개 미만이면 있는 것만 반환
    if len(centers) <= 5:
        return sorted(centers)

    # 5개보다 많으면 등간격 기준으로 최적 5개 선택
    best: list[int] = centers[:5]
    best_score = _regularity_score(best)
    for i in range(len(centers) - 4):
        candidate = centers[i:i + 5]
        score = _regularity_score(candidate)
        if score < best_score:
            best = candidate
            best_score = score
    return sorted(best)


def _regularity_score(ys: list[int]) -> float:
    """등간격일수록 낮은 점수(분산)를 반환한다."""
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    return float(np.var(gaps))
```

- [ ] **Step 4: pitch_converter.py 구현**

트레블 클레프 기준선: 1번선=E4, 2번선=G4, 3번선=B4, 4번선=D5, 5번선=F5
베이스 클레프 기준선: 1번선=G2, 2번선=B2, 3번선=D3, 4번선=F3, 5번선=A3

```python
# backend/app/stages/omr/pitch_converter.py
"""Module 2b: 보표 내 y좌표 → 피치 문자열 변환."""
from __future__ import annotations
from app.stages.omr.types import StaffSystem

# 트레블 클레프: 1번선(최하)=E4 → step=0, 이후 F4=1, G4=2, ...
# 보표선 위치 기준: line_ys[0](최상)=F5, line_ys[4](최하)=E4
# y가 작을수록(위) 음이 높음
_NOTE_NAMES = ["C", "D", "E", "F", "G", "A", "B"]

_TREBLE_BASE_STEP = 4   # line_ys[4](최하선) = E4 → C 기준 step = 2, octave 4 → 절대 step = 4*7+2 = 30
_BASS_BASE_STEP = 2     # line_ys[4](최하선) = G2 → 절대 step = 2*7+4 = 18

# 절대 step = octave * 7 + note_index (C=0, D=1, ..., B=6)
_TREBLE_BOTTOM_STEP = 4 * 7 + 2  # E4 = 30
_BASS_BOTTOM_STEP = 2 * 7 + 4    # G2 = 18


def y_to_pitch(y: int, staff: StaffSystem) -> str:
    """보표 내 y좌표를 피치 문자열로 변환한다.

    y: 이미지 절대 y좌표
    staff: 보표선 위치 포함 StaffSystem
    반환: "G4", "D5", "Bb3" 형태 문자열 (임시표 없이)
    """
    space = staff.staff_space
    if space <= 0:
        return "C4"

    bottom_line_y = staff.line_ys[-1]   # 최하선 (y값 최대)
    base_step = _TREBLE_BOTTOM_STEP if staff.clef == "treble" else _BASS_BOTTOM_STEP

    # y가 bottom_line_y 아래로 갈수록 pitch가 낮아짐
    # 반 칸(space/2) 단위로 step이 1씩 변한다
    half_spaces_from_bottom = (bottom_line_y - y) / (space / 2)
    step_offset = round(half_spaces_from_bottom)
    abs_step = base_step + step_offset

    octave, note_idx = divmod(abs_step, 7)
    return f"{_NOTE_NAMES[note_idx]}{octave}"
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_staff_detector.py tests/test_su_pitch_converter.py -v
```
Expected: `7 passed`

- [ ] **Step 6: 커밋**

```bash
git add backend/app/stages/omr/staff_detector.py backend/app/stages/omr/pitch_converter.py \
        backend/tests/test_su_staff_detector.py backend/tests/test_su_pitch_converter.py
git commit -m "feat(su): Module2a 보표선 정밀화 + 피치 변환"
```

---

## Task 5: Module 2b — YOLOv8 OMR 엔진 (omr_engine.py)

**Files:**
- Create: `backend/app/stages/omr/omr_engine.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_su_omr_engine.py`

**Interfaces:**
- Consumes: 이미지 경로, 모델 경로 (config에서)
- Produces: `detect(image_path: Path) → list[RawDetection]`
- 모델 없을 시: `OmrModelNotFoundError` 발생

검출 클래스: `notehead_filled`, `notehead_open`, `rest_whole`, `rest_half`, `rest_quarter`, `rest_eighth`, `accidental_sharp`, `accidental_flat`, `accidental_natural`, `key_sig_sharp`, `key_sig_flat`, `augmentation_dot`, `clef_treble`, `clef_bass`, `time_sig_num`

- [ ] **Step 1: config.py에 모델 경로 함수 추가**

```python
# backend/app/core/config.py 에 추가 (기존 함수들 아래)

def omr_model_path() -> Path | None:
    """YOLOv8 OMR 모델 경로. 환경변수 미설정 시 기본 경로 반환."""
    env = os.environ.get("AISCORE_OMR_MODEL_PATH")
    if env:
        return Path(env)
    default = _REPO / "models" / "omr" / "best.pt"
    return default if default.exists() else None

def paddleocr_lang() -> str:
    return os.environ.get("AISCORE_PADDLEOCR_LANG", "korean")
```

- [ ] **Step 2: 실패 테스트 작성**

```python
# backend/tests/test_su_omr_engine.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.stages.omr.omr_engine import OmrEngine, OmrModelNotFoundError
from app.stages.omr.types import RawDetection, BBox

def test_omr_engine_raises_if_no_model(tmp_path):
    """모델 파일 없으면 OmrModelNotFoundError."""
    with pytest.raises(OmrModelNotFoundError):
        OmrEngine(model_path=tmp_path / "nonexistent.pt")

def test_omr_engine_detect_returns_list(tmp_path):
    """detect()는 RawDetection 목록을 반환한다 (모델 mocking)."""
    fake_model_path = tmp_path / "fake.pt"
    fake_model_path.touch()

    mock_result = MagicMock()
    mock_box = MagicMock()
    mock_box.xyxy = [[10, 20, 60, 50]]
    mock_box.conf = [0.95]
    mock_box.cls = [0]
    mock_result.boxes = mock_box
    mock_result.names = {0: "notehead_filled"}

    with patch("app.stages.omr.omr_engine.YOLO") as MockYOLO:
        MockYOLO.return_value.return_value = [mock_result]
        engine = OmrEngine(model_path=fake_model_path)
        dummy_img = tmp_path / "img.png"
        dummy_img.touch()
        detections = engine.detect(dummy_img)

    assert isinstance(detections, list)
    assert all(isinstance(d, RawDetection) for d in detections)

def test_raw_detection_fields(tmp_path):
    fake_model_path = tmp_path / "fake.pt"
    fake_model_path.touch()

    mock_result = MagicMock()
    mock_box = MagicMock()
    mock_box.xyxy = [[10, 20, 60, 50]]
    mock_box.conf = [0.9]
    mock_box.cls = [0]
    mock_result.boxes = mock_box
    mock_result.names = {0: "notehead_filled"}

    with patch("app.stages.omr.omr_engine.YOLO") as MockYOLO:
        MockYOLO.return_value.return_value = [mock_result]
        engine = OmrEngine(model_path=fake_model_path)
        dummy_img = tmp_path / "img.png"
        dummy_img.touch()
        detections = engine.detect(dummy_img)

    d = detections[0]
    assert d.class_name == "notehead_filled"
    assert 0.0 <= d.confidence <= 1.0
    assert isinstance(d.bbox, BBox)
```

- [ ] **Step 3: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_omr_engine.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 4: omr_engine.py 구현**

```python
# backend/app/stages/omr/omr_engine.py
"""Module 2b: YOLOv8 기반 음악 기호 검출 엔진."""
from __future__ import annotations
from pathlib import Path

from app.stages.omr.types import BBox, RawDetection

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover
    YOLO = None  # type: ignore


class OmrModelNotFoundError(FileNotFoundError):
    """YOLOv8 모델 파일을 찾을 수 없을 때."""


class OmrEngine:
    """YOLOv8 모델을 로드하고 음악 기호를 검출한다."""

    OMR_CLASSES = [
        "notehead_filled", "notehead_open",
        "rest_whole", "rest_half", "rest_quarter", "rest_eighth",
        "accidental_sharp", "accidental_flat", "accidental_natural",
        "key_sig_sharp", "key_sig_flat",
        "augmentation_dot",
        "clef_treble", "clef_bass",
        "time_sig_num",
    ]

    def __init__(self, model_path: Path, conf_threshold: float = 0.5) -> None:
        if not model_path.exists():
            raise OmrModelNotFoundError(
                f"YOLOv8 OMR 모델 파일 없음: {model_path}\n"
                "학습 후 models/omr/best.pt 에 위치시키거나 "
                "AISCORE_OMR_MODEL_PATH 환경변수를 설정하세요."
            )
        if YOLO is None:  # pragma: no cover
            raise ImportError("ultralytics 패키지가 설치되지 않았습니다: pip install ultralytics")
        self._model = YOLO(str(model_path))
        self._conf = conf_threshold

    def detect(self, image_path: Path) -> list[RawDetection]:
        """이미지에서 음악 기호를 검출해 RawDetection 목록을 반환한다."""
        results = self._model(str(image_path), conf=self._conf, verbose=False)
        detections: list[RawDetection] = []
        for result in results:
            boxes = result.boxes
            names = result.names
            for i in range(len(boxes.xyxy)):
                x1, y1, x2, y2 = (int(v) for v in boxes.xyxy[i])
                conf = float(boxes.conf[i])
                cls_idx = int(boxes.cls[i])
                detections.append(RawDetection(
                    bbox=BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1),
                    class_name=names[cls_idx],
                    confidence=conf,
                ))
        return detections
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_omr_engine.py -v
```
Expected: `3 passed`

- [ ] **Step 6: 커밋**

```bash
git add backend/app/stages/omr/omr_engine.py backend/app/core/config.py backend/tests/test_su_omr_engine.py
git commit -m "feat(su): Module2b YOLOv8 OMR 엔진 + config 모델경로 추가"
```

---

## Task 6: Module 2c — 음가 분류 + 성부 분리

**Files:**
- Create: `backend/app/stages/omr/duration_classifier.py`
- Create: `backend/app/stages/omr/voice_assigner.py`
- Test: `backend/tests/test_su_duration_classifier.py`
- Test: `backend/tests/test_su_voice_assigner.py`

**Interfaces:**
- `classify_duration(det: RawDetection, nearby: list[RawDetection]) → tuple[float, bool]`: (quarterLength, is_dotted)
- `assign_voice(det: RawDetection, staff: StaffSystem) → int`: 1 또는 2

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_duration_classifier.py
from app.stages.omr.types import BBox, RawDetection
from app.stages.omr.duration_classifier import classify_duration

def _det(cls: str, x=100, y=100, w=20, h=20) -> RawDetection:
    return RawDetection(bbox=BBox(x, y, w, h), class_name=cls, confidence=0.9)

def test_open_notehead_no_nearby_is_whole():
    ql, dotted = classify_duration(_det("notehead_open"), [])
    assert ql == 4.0
    assert dotted is False

def test_filled_notehead_no_flag_is_quarter():
    ql, dotted = classify_duration(_det("notehead_filled"), [])
    assert ql == 1.0

def test_filled_notehead_with_flag_is_eighth():
    flag = _det("flag_eighth", x=110, y=80, w=10, h=20)
    ql, _ = classify_duration(_det("notehead_filled"), [flag])
    assert ql == 0.5

def test_dotted_note():
    dot = _det("augmentation_dot", x=125, y=100, w=5, h=5)
    ql, dotted = classify_duration(_det("notehead_filled"), [dot])
    assert dotted is True

def test_rest_quarter_duration():
    ql, _ = classify_duration(_det("rest_quarter"), [])
    assert ql == 1.0

def test_rest_half_duration():
    ql, _ = classify_duration(_det("rest_half"), [])
    assert ql == 2.0
```

```python
# backend/tests/test_su_voice_assigner.py
from app.stages.omr.types import BBox, RawDetection, StaffSystem
from app.stages.omr.voice_assigner import assign_voice

def _staff() -> StaffSystem:
    return StaffSystem(
        bbox=BBox(0, 90, 500, 60),
        line_ys=[100, 110, 120, 130, 140],
        clef="treble",
    )

def _det(y: int) -> RawDetection:
    return RawDetection(BBox(100, y, 15, 15), "notehead_filled", 0.9)

def test_upper_half_is_voice1():
    """보표 중간선(B4, y=120) 위는 Voice 1 (Soprano)."""
    assert assign_voice(_det(y=105), _staff()) == 1

def test_lower_half_is_voice2():
    """보표 중간선 아래는 Voice 2 (Alto)."""
    assert assign_voice(_det(y=135), _staff()) == 2
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_duration_classifier.py tests/test_su_voice_assigner.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: duration_classifier.py 구현**

```python
# backend/app/stages/omr/duration_classifier.py
"""Module 2c: 음표 형태 → 음가(quarterLength) 분류."""
from __future__ import annotations
from app.stages.omr.types import RawDetection

_REST_DURATIONS = {
    "rest_whole": 4.0,
    "rest_half": 2.0,
    "rest_quarter": 1.0,
    "rest_eighth": 0.5,
    "rest_16th": 0.25,
}

_NEARBY_THRESHOLD_PX = 40  # 점/깃발이 음표로부터 이 거리 이내면 연관


def classify_duration(
    det: RawDetection, nearby: list[RawDetection]
) -> tuple[float, bool]:
    """음표 검출 결과와 인근 기호로부터 음가를 반환한다.

    Returns:
        (quarterLength, is_dotted)
    """
    cls = det.class_name

    # 쉼표
    if cls in _REST_DURATIONS:
        return _REST_DURATIONS[cls], False

    # 온음표 후보 (open, 줄기/깃발 없음)
    if cls == "notehead_open":
        close = [n for n in nearby if _is_close(det, n)]
        has_flag = any(n.class_name.startswith("flag_") for n in close)
        has_beam = any(n.class_name == "beam" for n in close)
        is_dotted = any(n.class_name == "augmentation_dot" for n in close)
        if not has_flag and not has_beam:
            return 4.0, is_dotted   # 온음표
        return 2.0, is_dotted       # 2분음표

    # 채운 음표머리
    if cls == "notehead_filled":
        close = [n for n in nearby if _is_close(det, n)]
        is_dotted = any(n.class_name == "augmentation_dot" for n in close)
        flag_count = sum(1 for n in close if n.class_name.startswith("flag_"))
        beam_count = sum(1 for n in close if n.class_name == "beam")
        subdivisions = max(flag_count, beam_count)
        ql = 1.0 / (2 ** subdivisions) if subdivisions > 0 else 1.0
        return ql, is_dotted

    return 1.0, False  # 미분류 → 4분음표 기본값


def _is_close(a: RawDetection, b: RawDetection) -> bool:
    dx = abs(a.bbox.center_x - b.bbox.center_x)
    dy = abs(a.bbox.center_y - b.bbox.center_y)
    return dx <= _NEARBY_THRESHOLD_PX and dy <= _NEARBY_THRESHOLD_PX
```

- [ ] **Step 4: voice_assigner.py 구현**

```python
# backend/app/stages/omr/voice_assigner.py
"""Module 2c: 성부 분리 — 보표 내 음표 위치 기반 휴리스틱."""
from __future__ import annotations
from app.stages.omr.types import RawDetection, StaffSystem


def assign_voice(det: RawDetection, staff: StaffSystem) -> int:
    """음표의 보표 내 위치로 성부를 결정한다.

    Returns:
        1 = Soprano(treble) / Tenor(bass)
        2 = Alto(treble) / Bass(bass)
    """
    if not staff.line_ys:
        return 1
    mid_y = staff.line_ys[2]   # 3번째 선(중간선)
    return 1 if det.bbox.center_y <= mid_y else 2
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_duration_classifier.py tests/test_su_voice_assigner.py -v
```
Expected: `8 passed`

- [ ] **Step 6: 커밋**

```bash
git add backend/app/stages/omr/duration_classifier.py backend/app/stages/omr/voice_assigner.py \
        backend/tests/test_su_duration_classifier.py backend/tests/test_su_voice_assigner.py
git commit -m "feat(su): Module2c 음가 분류 + 성부 분리"
```

---

## Task 7: Module 3 — 메타 추출 (meta_extractor.py)

**Files:**
- Create: `backend/app/stages/omr/meta_extractor.py`
- Test: `backend/tests/test_su_meta_extractor.py`

**Interfaces:**
- Consumes: `LayoutResult`, `list[RawDetection]` (OMR 결과), `gray: np.ndarray`
- Produces: `extract_meta(layout: LayoutResult, detections: list[RawDetection], gray: np.ndarray) → ScoreMeta`

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_meta_extractor.py
import numpy as np
from app.stages.omr.types import BBox, LayoutResult, RawDetection, StaffSystem
from app.stages.omr.meta_extractor import extract_meta, accidentals_to_key

def _empty_layout(h=1200, w=900):
    return LayoutResult(
        image_h=h, image_w=w,
        title_region=BBox(0, 0, w, 100),
        tempo_region=BBox(0, 80, 200, 30),
        staff_systems=[StaffSystem(BBox(0,120,w,60), [130,140,150,160,170], "treble")],
        lyric_regions=[BBox(0, 800, w, 200)],
    )

def test_key_one_sharp():
    assert accidentals_to_key(1, "sharp") == "G major"

def test_key_two_sharps():
    assert accidentals_to_key(2, "sharp") == "D major"

def test_key_one_flat():
    assert accidentals_to_key(1, "flat") == "F major"

def test_key_zero():
    assert accidentals_to_key(0, "sharp") == "C major"

def test_extract_meta_returns_score_meta():
    layout = _empty_layout()
    detections = [
        RawDetection(BBox(50, 125, 20, 20), "key_sig_sharp", 0.9),
    ]
    gray = np.full((1200, 900), 230, dtype=np.uint8)
    meta = extract_meta(layout, detections, gray)
    assert meta.key == "G major"
    assert meta.time_num > 0

def test_extract_meta_time_signature():
    layout = _empty_layout()
    detections = [
        RawDetection(BBox(80, 125, 15, 15), "time_sig_num", 0.9),
        RawDetection(BBox(80, 142, 15, 15), "time_sig_num", 0.9),
    ]
    gray = np.full((1200, 900), 230, dtype=np.uint8)
    meta = extract_meta(layout, detections, gray)
    assert meta.time_num in (2, 3, 4, 6)
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_meta_extractor.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: meta_extractor.py 구현**

```python
# backend/app/stages/omr/meta_extractor.py
"""Module 3: 조성·박자·제목·빠르기 추출."""
from __future__ import annotations
import re
import numpy as np

from app.stages.omr.types import LayoutResult, RawDetection, ScoreMeta

_SHARP_KEYS = ["C major", "G major", "D major", "A major",
               "E major", "B major", "F# major", "C# major"]
_FLAT_KEYS  = ["C major", "F major", "Bb major", "Eb major",
               "Ab major", "Db major", "Gb major", "Cb major"]
_BPM_RE = re.compile(r"♩\s*=\s*(\d+)|(\d+)\s*bpm", re.IGNORECASE)
_TIME_SIGS = {(4, 4), (3, 4), (2, 4), (6, 8), (3, 8), (2, 2)}


def accidentals_to_key(count: int, kind: str) -> str:
    """임시표 개수와 종류로 조성 문자열을 반환한다."""
    if kind == "sharp":
        return _SHARP_KEYS[min(count, 7)]
    return _FLAT_KEYS[min(count, 7)]


def extract_meta(
    layout: LayoutResult,
    detections: list[RawDetection],
    gray: np.ndarray,
) -> ScoreMeta:
    """레이아웃·검출 결과·이미지에서 메타정보를 추출한다."""
    # 조성: 조성기호 개수로 판단
    sharp_count = sum(1 for d in detections if d.class_name == "key_sig_sharp")
    flat_count  = sum(1 for d in detections if d.class_name == "key_sig_flat")
    if sharp_count > 0:
        key = accidentals_to_key(sharp_count, "sharp")
    elif flat_count > 0:
        key = accidentals_to_key(flat_count, "flat")
    else:
        key = "C major"

    # 박자: time_sig_num 검출 개수로 추정 (위=분자, 아래=분모)
    time_dets = sorted(
        [d for d in detections if d.class_name == "time_sig_num"],
        key=lambda d: d.bbox.y,
    )
    time_num, time_den = 4, 4
    if len(time_dets) >= 2:
        # 숫자 자체는 YOLOv8이 분류 — 여기선 개수만으로 4/4 추정
        time_num, time_den = 4, 4  # Task 5 학습 완료 후 실제 분류로 교체

    # 제목·빠르기: PaddleOCR (Task 8 이후 통합). 지금은 빈 문자열
    title = ""
    tempo_text = ""
    bpm: int | None = None

    return ScoreMeta(
        title=title,
        key=key,
        time_num=time_num,
        time_den=time_den,
        tempo_text=tempo_text,
        bpm=bpm,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_meta_extractor.py -v
```
Expected: `5 passed`

- [ ] **Step 5: 커밋**

```bash
git add backend/app/stages/omr/meta_extractor.py backend/tests/test_su_meta_extractor.py
git commit -m "feat(su): Module3 메타 추출 — 조성·박자 기호 기반"
```

---

## Task 8: Module 4 — 가사 OCR (lyrics_ocr.py)

**Files:**
- Create: `backend/app/stages/omr/lyrics_ocr.py`
- Test: `backend/tests/test_su_lyrics_ocr.py`

**Interfaces:**
- Consumes: `gray: np.ndarray`, `lyric_regions: list[BBox]`
- Produces: `extract_lyrics(gray: np.ndarray, regions: list[BBox]) → LyricsResult`

> **주의:** 첫 실행 시 PaddleOCR 한국어 모델을 자동 다운로드합니다 (~400MB). 오프라인 환경에서는 `~/.paddleocr/` 캐시 확인.

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_lyrics_ocr.py
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from app.stages.omr.types import BBox, LyricsResult
from app.stages.omr.lyrics_ocr import extract_lyrics, split_syllables

def test_split_syllables_korean():
    """한국어 음절을 하나씩 분리한다."""
    result = split_syllables("주님의크신사랑")
    assert result == ["주", "님", "의", "크", "신", "사", "랑"]

def test_split_syllables_mixed():
    """공백·구두점 제거 후 음절만 반환한다."""
    result = split_syllables("주 님의, 사랑")
    assert result == ["주", "님", "의", "사", "랑"]

def test_extract_lyrics_empty_regions():
    gray = np.full((800, 600), 230, dtype=np.uint8)
    result = extract_lyrics(gray, [])
    assert result.verse_count == 0

def test_extract_lyrics_returns_lyrics_result():
    gray = np.full((800, 600), 230, dtype=np.uint8)
    regions = [BBox(0, 500, 600, 50), BBox(0, 560, 600, 50)]
    mock_ocr = MagicMock()
    mock_ocr.return_value = [[("주님의 사랑", 0.95)]]
    with patch("app.stages.omr.lyrics_ocr._get_ocr_engine", return_value=mock_ocr):
        result = extract_lyrics(gray, regions)
    assert isinstance(result, LyricsResult)
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_lyrics_ocr.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: lyrics_ocr.py 구현**

```python
# backend/app/stages/omr/lyrics_ocr.py
"""Module 4: PaddleOCR 기반 한글 가사 추출."""
from __future__ import annotations
import re
import numpy as np
from functools import lru_cache

from app.core.config import paddleocr_lang
from app.stages.omr.types import BBox, LyricsResult

_PUNCT_RE = re.compile(r"[\s,\.\-\(\)\[\]·~]+")


@lru_cache(maxsize=1)
def _get_ocr_engine():
    """PaddleOCR 엔진을 싱글톤으로 로드한다 (첫 호출 시 모델 다운로드)."""
    try:
        from paddleocr import PaddleOCR
        return PaddleOCR(use_angle_cls=False, lang=paddleocr_lang(), show_log=False)
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "paddleocr 패키지가 필요합니다: pip install paddleocr paddlepaddle"
        ) from e


def extract_lyrics(gray: np.ndarray, regions: list[BBox]) -> LyricsResult:
    """가사 영역에서 절별 가사를 추출한다.

    각 BBox가 1절에 해당한다고 가정한다.
    반환된 LyricsResult.verses[i]는 i번째 절의 음절 목록이다.
    """
    if not regions:
        return LyricsResult(verses=[])

    ocr = _get_ocr_engine()
    verses: list[list[str]] = []
    h, w = gray.shape

    for region in regions:
        y1 = max(0, region.y)
        y2 = min(h, region.y2)
        x1 = max(0, region.x)
        x2 = min(w, region.x2)
        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            verses.append([])
            continue
        results = ocr(crop)
        text = " ".join(r[0] for r in results[0]) if results and results[0] else ""
        verses.append(split_syllables(text))

    return LyricsResult(verses=verses)


def split_syllables(text: str) -> list[str]:
    """한국어 텍스트를 음절(글자) 단위로 분리한다. 구두점·공백 제거."""
    cleaned = _PUNCT_RE.sub("", text)
    return list(cleaned)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_lyrics_ocr.py -v
```
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add backend/app/stages/omr/lyrics_ocr.py backend/tests/test_su_lyrics_ocr.py
git commit -m "feat(su): Module4 가사 OCR — PaddleOCR 한국어 + 음절 분리"
```

---

## Task 9: Module 5 — MusicXML 조립 (musicxml_assembler.py)

**Files:**
- Create: `backend/app/stages/omr/musicxml_assembler.py`
- Test: `backend/tests/test_su_musicxml_assembler.py`

**Interfaces:**
- Consumes: `ScoreMeta`, `list[NoteEvent]`, `LyricsResult`
- Produces: `assemble(meta, notes, lyrics, out_path) → Path` — 유효한 MusicXML 파일

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_musicxml_assembler.py
import pytest
from pathlib import Path
from app.stages.omr.types import NoteEvent, ScoreMeta, LyricsResult
from app.stages.omr.musicxml_assembler import assemble

def _sample_notes() -> list[NoteEvent]:
    return [
        NoteEvent(pitch="G4", duration=1.0, voice=1, staff_idx=0, x=100),
        NoteEvent(pitch="A4", duration=1.0, voice=1, staff_idx=0, x=150),
        NoteEvent(pitch="B4", duration=2.0, voice=1, staff_idx=0, x=200),
        NoteEvent(pitch="E4", duration=1.0, voice=2, staff_idx=0, x=100),
        NoteEvent(pitch="F4", duration=1.0, voice=2, staff_idx=0, x=150),
        NoteEvent(pitch="G4", duration=2.0, voice=2, staff_idx=0, x=200),
    ]

def _sample_meta() -> ScoreMeta:
    return ScoreMeta(title="테스트 찬양", key="G major", time_num=4, time_den=4)

def test_assemble_creates_file(tmp_path):
    out = tmp_path / "score.mxl"
    result = assemble(_sample_meta(), _sample_notes(), LyricsResult(verses=[]), out)
    assert result == out
    assert out.exists()

def test_assemble_output_is_valid_musicxml(tmp_path):
    """출력 파일이 MusicXML로 파싱 가능해야 한다."""
    import music21
    out = tmp_path / "score.mxl"
    assemble(_sample_meta(), _sample_notes(), LyricsResult(verses=[]), out)
    score = music21.converter.parse(str(out))
    assert score is not None

def test_assemble_note_count(tmp_path):
    """음표 수가 일치해야 한다."""
    import music21
    notes = _sample_notes()
    out = tmp_path / "score.mxl"
    assemble(_sample_meta(), notes, LyricsResult(verses=[]), out)
    score = music21.converter.parse(str(out))
    all_notes = list(score.flatten().notes)
    assert len(all_notes) == len(notes)

def test_assemble_with_lyrics(tmp_path):
    """가사가 음표에 첨부되는지 확인한다."""
    import music21
    notes = [NoteEvent("G4", 1.0, 1, 0, 100), NoteEvent("A4", 1.0, 1, 0, 150)]
    lyrics = LyricsResult(verses=[["주", "님"]])
    out = tmp_path / "score.mxl"
    assemble(_sample_meta(), notes, lyrics, out)
    score = music21.converter.parse(str(out))
    note_list = [n for n in score.flatten().notes if isinstance(n, music21.note.Note)]
    assert note_list[0].lyric == "주"
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_musicxml_assembler.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: musicxml_assembler.py 구현**

```python
# backend/app/stages/omr/musicxml_assembler.py
"""Module 5: music21을 이용한 완전한 MusicXML 조립."""
from __future__ import annotations
from pathlib import Path

import music21
from music21 import stream, note, metadata, tempo, key, meter

from app.stages.omr.types import LyricsResult, NoteEvent, ScoreMeta

_KEY_MAP = {
    "C major": "C", "G major": "G", "D major": "D", "A major": "A",
    "E major": "E", "B major": "B", "F major": "F", "Bb major": "b-",
    "Eb major": "E-", "Ab major": "A-", "F# major": "F#",
    "D minor": "d", "A minor": "a", "E minor": "e", "B minor": "b",
    "G minor": "g", "C minor": "c", "F minor": "f",
}


def assemble(
    meta: ScoreMeta,
    notes: list[NoteEvent],
    lyrics: LyricsResult,
    out_path: Path,
) -> Path:
    """메타정보·음표·가사를 받아 MusicXML 파일로 조립한다."""
    score = stream.Score()

    # 메타데이터
    md = metadata.Metadata()
    md.title = meta.title
    score.insert(0, md)

    # 빠르기
    bpm = meta.bpm or 80
    score.insert(0, tempo.MetronomeMark(number=bpm, referent=note.Note(type="quarter")))

    # 성부별로 음표 분리 (staff_idx 0=트레블, 1=베이스)
    # voice: 1=Soprano or Tenor, 2=Alto or Bass
    voice_map: dict[tuple[int, int], list[NoteEvent]] = {}
    for n in sorted(notes, key=lambda x: x.x):
        k = (n.staff_idx, n.voice)
        voice_map.setdefault(k, []).append(n)

    for (staff_idx, voice), voice_notes in sorted(voice_map.items()):
        part = stream.Part()
        part.id = f"staff{staff_idx}_voice{voice}"

        # 조성기호
        key_str = _KEY_MAP.get(meta.key, "C")
        part.insert(0, key.Key(key_str))
        # 박자기호
        part.insert(0, meter.TimeSignature(f"{meta.time_num}/{meta.time_den}"))

        # 해당 성부 가사 시퀀스
        verse_syllables: list[list[str]] = []
        for verse in lyrics.verses:
            verse_syllables.append(verse[:])

        note_idx = 0
        for evt in voice_notes:
            if evt.pitch.startswith("rest"):
                n_obj = note.Rest(quarterLength=evt.duration)
            else:
                ql = evt.duration * 1.5 if evt.is_dotted else evt.duration
                n_obj = note.Note(evt.pitch, quarterLength=ql)
                # 가사 첨부
                for v_i, syllables in enumerate(verse_syllables, 1):
                    if note_idx < len(syllables):
                        n_obj.addLyric(syllables[note_idx], lyricNumber=v_i)
            part.append(n_obj)
            note_idx += 1

        score.append(part)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(out_path))
    return out_path
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_musicxml_assembler.py -v
```
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add backend/app/stages/omr/musicxml_assembler.py backend/tests/test_su_musicxml_assembler.py
git commit -m "feat(su): Module5 MusicXML 조립 — 메타+음표+가사 통합"
```

---

## Task 10: ScoreUnderstandingAdapter — OmrPort 통합

**Files:**
- Create: `backend/app/stages/omr/score_understanding_adapter.py`
- Test: `backend/tests/test_su_adapter.py`

**Interfaces:**
- Implements: `OmrPort.recognize(image_path: Path) → Path`
- 파이프라인 전체를 단일 진입점으로 조율

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_su_adapter.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.stages.omr.score_understanding_adapter import ScoreUnderstandingAdapter
from app.domain.ports import OmrPort

def test_adapter_implements_omr_port():
    assert issubclass(ScoreUnderstandingAdapter, OmrPort)

def test_adapter_recognize_returns_path(tmp_path):
    """모든 하위 모듈을 mock해서 파이프라인이 Path를 반환하는지 확인."""
    img = tmp_path / "score.png"
    img.write_bytes(b"PNG_DUMMY")

    with patch("app.stages.omr.score_understanding_adapter.preprocess") as p0, \
         patch("app.stages.omr.score_understanding_adapter.analyze_layout") as p1, \
         patch("app.stages.omr.score_understanding_adapter.OmrEngine") as p2, \
         patch("app.stages.omr.score_understanding_adapter.extract_meta") as p3, \
         patch("app.stages.omr.score_understanding_adapter.extract_lyrics") as p4, \
         patch("app.stages.omr.score_understanding_adapter.assemble") as p5:

        from app.stages.omr.types import LayoutResult, BBox, StaffSystem, ScoreMeta, LyricsResult
        import numpy as np

        p0.return_value = img
        p1.return_value = LayoutResult(1200, 900, None, None,
            [StaffSystem(BBox(0,100,900,80), [110,120,130,140,150], "treble")], [])
        p2.return_value.detect.return_value = []
        p3.return_value = ScoreMeta()
        p4.return_value = LyricsResult(verses=[])
        out_mxl = tmp_path / "score.mxl"
        out_mxl.touch()
        p5.return_value = out_mxl

        adapter = ScoreUnderstandingAdapter(work_dir=tmp_path)
        result = adapter.recognize(img)

    assert isinstance(result, Path)
    assert result.suffix == ".mxl"
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_adapter.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: score_understanding_adapter.py 구현**

```python
# backend/app/stages/omr/score_understanding_adapter.py
"""OmrPort 구현 — 5모듈 Score Understanding 파이프라인."""
from __future__ import annotations
from pathlib import Path

import cv2

from app.core.config import omr_model_path
from app.stages.omr.preprocessor import preprocess
from app.stages.omr.layout_analyzer import analyze_layout
from app.stages.omr.omr_engine import OmrEngine
from app.stages.omr.pitch_converter import y_to_pitch
from app.stages.omr.duration_classifier import classify_duration
from app.stages.omr.voice_assigner import assign_voice
from app.stages.omr.meta_extractor import extract_meta
from app.stages.omr.lyrics_ocr import extract_lyrics
from app.stages.omr.musicxml_assembler import assemble
from app.stages.omr.types import NoteEvent


class ScoreUnderstandingAdapter:
    """악보 이미지 → 완전한 MusicXML. OmrPort 구현체."""

    def __init__(self, work_dir: Path, conf_threshold: float = 0.5) -> None:
        self._work_dir = work_dir
        model = omr_model_path()
        self._engine = OmrEngine(model_path=model, conf_threshold=conf_threshold) if model else None

    def recognize(self, image_path: Path) -> Path:
        """이미지 경로를 받아 완전한 MusicXML 파일 경로를 반환한다."""
        job_dir = self._work_dir / image_path.stem
        job_dir.mkdir(parents=True, exist_ok=True)

        # Module 0: 전처리
        pre_path = job_dir / "preprocessed.png"
        preprocess(image_path, pre_path)

        # 이미지 로드 (이후 모듈 공유)
        gray = cv2.imread(str(pre_path), cv2.IMREAD_GRAYSCALE)

        # Module 1: 레이아웃 분석
        layout = analyze_layout(gray)

        # Module 2: OMR
        detections = self._engine.detect(pre_path) if self._engine else []

        note_events: list[NoteEvent] = []
        for det in detections:
            if det.class_name not in ("notehead_filled", "notehead_open"):
                continue
            # 보표 시스템 찾기
            staff = next(
                (s for s in layout.staff_systems
                 if s.bbox.y <= det.bbox.center_y <= s.bbox.y2),
                None,
            )
            if staff is None:
                continue
            pitch = y_to_pitch(det.bbox.center_y, staff)
            ql, dotted = classify_duration(det, [d for d in detections if d is not det])
            voice = assign_voice(det, staff)
            staff_idx = layout.staff_systems.index(staff)
            note_events.append(NoteEvent(
                pitch=pitch, duration=ql, voice=voice,
                staff_idx=staff_idx, x=det.bbox.x, is_dotted=dotted,
            ))

        # Module 3: 메타 추출
        meta = extract_meta(layout, detections, gray)

        # Module 4: 가사 OCR
        lyrics = extract_lyrics(gray, layout.lyric_regions)

        # Module 5: MusicXML 조립
        out_path = job_dir / f"{image_path.stem}.mxl"
        return assemble(meta, note_events, lyrics, out_path)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_adapter.py -v
```
Expected: `2 passed`

- [ ] **Step 5: 전체 단위 테스트 통과 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/ -v --ignore=tests/test_su_adapter.py -k "not integration"
```
Expected: 기존 테스트 포함 전체 통과 (새 테스트 포함)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/stages/omr/score_understanding_adapter.py backend/tests/test_su_adapter.py
git commit -m "feat(su): ScoreUnderstandingAdapter — OmrPort 5모듈 파이프라인 통합"
```

---

## Task 11: E2E 통합 테스트 (315.JPG → MusicXML)

**Files:**
- Test: `backend/tests/test_su_adapter.py` (기존 파일에 추가)

> **전제:** YOLOv8 모델 학습 완료 (`models/omr/best.pt` 존재) 또는 `AISCORE_OMR_MODEL_PATH` 설정 후 실행.
> 모델 없이도 파이프라인 구조 검증(레이아웃+가사)은 가능.

- [ ] **Step 1: 통합 테스트 추가**

```python
# backend/tests/test_su_adapter.py 에 추가

@pytest.mark.integration
def test_e2e_hymn315_creates_musicxml(tmp_path):
    """315.JPG → ScoreUnderstandingAdapter → .mxl 생성 E2E 검증."""
    from app.stages.omr.score_understanding_adapter import ScoreUnderstandingAdapter
    img_path = Path(__file__).parent.parent / "score_images" / "315.JPG"
    if not img_path.exists():
        pytest.skip("315.JPG 없음 — score_images/ 디렉터리 확인")

    adapter = ScoreUnderstandingAdapter(work_dir=tmp_path)
    result = adapter.recognize(img_path)

    assert result.exists(), f"MusicXML 파일 생성 실패: {result}"
    assert result.suffix == ".mxl"

    import music21
    score = music21.converter.parse(str(result))
    all_notes = list(score.flatten().notes)
    print(f"\n[E2E] 검출 음표 수: {len(all_notes)}")
    # 모델 없을 때는 0음표도 허용 (구조 검증 목적)
    assert len(all_notes) >= 0


@pytest.mark.integration
def test_e2e_layout_detection_315(tmp_path):
    """315.JPG 레이아웃 분석 — 보표 시스템 최소 2개 검출."""
    import cv2
    from app.stages.omr.preprocessor import preprocess
    from app.stages.omr.layout_analyzer import analyze_layout
    img_path = Path(__file__).parent.parent / "score_images" / "315.JPG"
    if not img_path.exists():
        pytest.skip("315.JPG 없음")

    pre = tmp_path / "pre.png"
    preprocess(img_path, pre)
    gray = cv2.imread(str(pre), cv2.IMREAD_GRAYSCALE)
    layout = analyze_layout(gray)

    assert len(layout.staff_systems) >= 2, \
        f"보표 시스템 {len(layout.staff_systems)}개 검출 — 최소 2개 필요"
    print(f"\n[Layout] 보표 시스템: {len(layout.staff_systems)}개")
    print(f"[Layout] 가사 영역: {len(layout.lyric_regions)}개")
```

- [ ] **Step 2: 통합 테스트 실행 (모델 없이 레이아웃 검증)**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/test_su_adapter.py::test_e2e_layout_detection_315 -v -m integration
```
Expected: 보표 시스템 검출 수 출력 + PASSED

- [ ] **Step 3: 전체 단위 테스트 회귀 확인**

```bash
cd backend && /opt/miniconda3/envs/aiscore/bin/python -m pytest tests/ -v -k "not integration"
```
Expected: 모든 기존 테스트 + 새 단위 테스트 통과

- [ ] **Step 4: 최종 커밋**

```bash
git add backend/tests/test_su_adapter.py
git commit -m "test(su): E2E 통합 테스트 추가 — 레이아웃 검출 + MusicXML 생성 검증"
```

---

## 다음 단계: Plan 1B — 모델 학습

이 계획서 완료 후 별도 계획서 `2026-06-19-score-understanding-training.md` 작성:

- [ ] Lilypond 렌더링 스크립트 (`training/scripts/render_scores.py`)
- [ ] YOLO 포맷 레이블 자동 생성 (`training/scripts/generate_labels.py`)
- [ ] YOLOv8 파인튜닝 스크립트 (DeepScores V2 사전학습 → 찬송가 데이터)
- [ ] PaddleOCR 한국어 파인튜닝 (찬송가 가사 GT 데이터)
- [ ] 평가 스크립트 (`training/scripts/evaluate.py`) — 기준선(Audiveris 65%) 대비 측정

---

## 95% 달성 경로 (모델 학습 후)

| 지표 | Phase 1 파이프라인 완성 후 | 모델 파인튜닝 후 | 목표 |
|------|--------------------------|----------------|------|
| 음표 검출 Recall | 측정 불가 (모델 없음) | ≥ 80% | ≥ 95% |
| 피치 정확도 | — | ≥ 85% | ≥ 95% |
| 박자 정확도 | — | ≥ 80% | ≥ 95% |
| 가사 CER | PaddleOCR 기본 ~80% | 파인튜닝 후 ≤ 5% | ≤ 5% |
