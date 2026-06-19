# 악보 이해 파이프라인 설계 — Score Understanding Pipeline

> **작성일:** 2026-06-19
> **배경:** Audiveris 규칙 기반 OMR의 65% 정확도 한계 → 악보 이미지에서 메타정보·음표(피치+박자)·가사를 추출해 완전한 MusicXML을 생성하는 AI 파이프라인 재설계.
> **연계:** [ROADMAP.md](../../ROADMAP.md) | [DL-OMR 설계](./2026-06-19-dl-omr-design.md) | [CLAUDE.md](../../../CLAUDE.md)

---

## 1. 목표 및 범위

### 1.1 목표

악보 이미지 한 장을 입력받아 **완전한 MusicXML 파일** 하나를 출력한다.

완전한 MusicXML = **메타정보** (제목·조성·박자·빠르기) + **음표** (피치+박자 전성부) + **가사** (모든 절)

### 1.2 성능 목표

| 태스크 | 지표 | 목표 |
|--------|------|------|
| 음표 검출 (Recall) | 정답 음표 중 검출 비율 | ≥ 95% |
| 피치 정확도 | 검출 음표 중 피치 정확 비율 | ≥ 95% |
| 박자 정확도 | 검출 음표 중 박자 정확 비율 | ≥ 95% |
| 가사 OCR (CER) | 문자 오류율 | ≤ 5% |
| 메타 정확도 | 조성/박자 완전 일치, 제목 CER | ≥ 95% |

**기준선 (현재 Audiveris):** 소프라노 검출 65%, 4마디 전체 누락.

### 1.3 입력 범위

| Phase | 입력 | 비고 |
|-------|------|------|
| **Phase 1** | 한국 찬송가 SATB 이미지 | 4성부, 규격화 레이아웃 |
| **Phase 1** | 1부 찬양 악보 이미지 | 단성부, 반주 없음 |
| **Phase 2** | 칸타타 PDF (4성부 + 악기) | 원하는 파트 선택 → MusicXML |

---

## 2. 시스템 아키텍처

### 2.1 전체 흐름

```
이미지 / PDF
     ↓
┌─────────────────────────────────────────────┐
│  Module 0: 문서 전처리                       │
│  PDF분할 · DPI정규화(300dpi) · 이진화 · 기울기보정 │
└─────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────┐
│  Module 1: 레이아웃 분석                     │
│  보표시스템 검출 · 파트레이블인식(Phase2)     │
│  → 제목영역 / 보표영역 / 빠르기표영역 / 가사영역 │
└─────────────────────────────────────────────┘
     ↓ 영역별 분기 (병렬 처리 가능)
     │
     ├─────────────────────────────────────────┐
     │  Module 2: OMR                           │
     │  [피치] YOLOv8 → 음표머리 검출 → 보표위치→피치 │
     │  [박자] 음표형태 분류 → 음가(합성데이터학습) │
     │  [성부] 줄기방향 → S/A/T/B 분리          │
     └─────────────────────────────────────────┘
     │
     ├─────────────────────────────────────────┐
     │  Module 3: 메타 추출                     │
     │  조성·박자 = OMR 기호 공유               │
     │  제목·빠르기말 = PaddleOCR               │
     └─────────────────────────────────────────┘
     │
     └─────────────────────────────────────────┐
        Module 4: 가사 OCR                      │
        PaddleOCR(한글) 파인튜닝 → 절별 가사    │
        음절 분리 → 음표 연결 준비              │
     └─────────────────────────────────────────┘
                       ↓
     ┌─────────────────────────────────────────┐
     │  Module 5: MusicXML 조립 (music21)       │
     │  메타 헤더 + 음표 + 가사(절번호) → .mxl  │
     └─────────────────────────────────────────┘
```

### 2.2 헥사고날 아키텍처 연동

현재 `OmrPort` 인터페이스를 **변경 없이** 유지. 내부 구현만 교체.

```python
# backend/app/stages/omr/score_understanding_adapter.py
class ScoreUnderstandingAdapter:
    """OmrPort 구현 — 5모듈 파이프라인 → 완전한 MusicXML 반환."""

    def recognize(self, image_path: Path) -> Path:
        img = self._module0_preprocess(image_path)
        regions = self._module1_layout(img)
        notes = self._module2_omr(regions.staves)
        meta = self._module3_meta(regions.meta, notes.key_sig, notes.time_sig)
        lyrics = self._module4_lyrics(regions.lyrics)
        return self._module5_assemble(meta, notes, lyrics)
```

오케스트레이터(`orchestrator.py`)는 변경 없음.

---

## 3. 모듈 상세 설계

### Module 0 — 문서 전처리

**목적:** 모든 입력을 300 DPI 이진 이미지로 정규화.

| 기능 | 도구/방법 | 근거 |
|------|---------|------|
| PDF → 이미지 | `pdf2image` (poppler) | Phase 2 PDF 처리 |
| 해상도 정규화 | OpenCV 리샘플링 → 300 DPI | Audiveris 실증: 저해상도 PAGE 실패 |
| 이진화 | Otsu thresholding | 인쇄 악보 표준 기법 |
| 기울기 보정 | Hough transform + affine | 스캔 악보 편차 대비 |
| 크기 상한 | 최대 4096px 장변 리샘플링 | OOM 방어 (§12 규칙) |

---

### Module 1 — 레이아웃 분석

**Phase 1 (찬송가): 투영 프로파일 기반 규칙**

찬송가 레이아웃은 규격화됨 → 수평 투영 프로파일(흑백 픽셀 밀도)로 영역 분리.

```
상단 10%   → 제목 영역
중간 60%   → 보표 시스템 (보표선 밀도 피크로 검출)
하단 30%   → 가사 영역 (텍스트 라인 밀도)
보표 상단  → 빠르기표 영역
```

**Phase 2 (칸타타): YOLOv8 레이아웃 검출기 추가**

- 파트 레이블(`Soprano`, `Alto`, `Violin I` 등) 검출 → OCR
- 브레이스/브래킷 그룹 인식 → 인스트루먼트 그룹 분류
- 학습 데이터: 합성 악보 스코어 레이아웃 어노테이션

**출력 구조:**

```python
@dataclass
class LayoutResult:
    title_region: BBox
    tempo_region: BBox
    staff_systems: list[StaffSystem]   # 보표 시스템 목록
    lyric_regions: list[BBox]          # 절별 가사 영역
    part_labels: list[str]             # Phase 2: ["Soprano", "Alto", ...]
```

---

### Module 2 — OMR (음표 인식)

#### 2-1. 피치 인식 (계이름) — 지도학습

**모델:** YOLOv8n (음표머리 검출) + 피치 분류기

```
[YOLOv8] 음표머리 바운딩박스 검출
     ↓
[보표선 위치 계산] 검출된 보표선 5개 → 라인/스페이스 격자
     ↓
[피치 분류] 음표머리 y좌표 → 보표 위치 → 음이름(C4, D4, ...)
     ↓ 올림표/내림표/제자리표 반영
최종 피치
```

**학습 데이터:** 실제 찬송가 스캔 이미지 + GT 계이름 레이블 (직접 제공)

**검출 클래스:**
- notehead_filled (4분음표 이하)
- notehead_open (온음표/2분음표)
- accidental_sharp / flat / natural
- rest_quarter / rest_half / rest_whole
- clef_treble / clef_bass

#### 2-2. 박자 인식 (음가) — 합성 데이터 지도학습

**핵심 원칙:** 실제 스캔 이미지에 박자 레이블을 수동으로 달지 않는다. 대신 MusicXML → 렌더링으로 자동 생성.

```
CPDL / MuseScore 찬송가 MusicXML (~500곡)
     ↓ Lilypond 렌더링 (해상도/노이즈/기울기 증강)
합성 이미지 (자동 박자 레이블 포함)
     ↓
박자 분류기 학습 (음표머리 패치 → 음가 분류)
```

**시각적 특징 기반 분류 규칙 (보완):**

```
빈 타원, 줄기 없음          → 온음표 (whole)
빈 타원 + 줄기              → 2분음표 (half)
채운 타원 + 줄기            → 4분음표 (quarter)
채운 타원 + 줄기 + 깃발 1  → 8분음표 (eighth)
채운 타원 + 줄기 + 깃발 2  → 16분음표 (16th)
빔(beam) 연결               → 깃발 수 대체
음표 옆 점(·)               → 점음표 (duration × 1.5)
```

#### 2-3. 성부 분리 (Voice Assignment)

```
트레블 보표:
  줄기 위쪽 → 소프라노 (Voice 1)
  줄기 아래쪽 → 알토 (Voice 2)

베이스 보표:
  줄기 위쪽 → 테너 (Voice 1)
  줄기 아래쪽 → 베이스 (Voice 2)
```

#### 2-4. 단계적 업그레이드 경로

```
1차 (Phase 1):  YOLOv8 파이프라인  ← 즉시 착수
2차 (Phase 1+): SMT++ 파인튜닝     ← 찬송가 데이터 500곡 이상 시 교체
3차 (Phase 2):  E2E 트랜스포머     ← 칸타타 대응
```

어댑터 교체만으로 전환 가능 (오케스트레이터 변경 없음).

---

### Module 3 — 메타 추출

| 메타 항목 | 방법 | 상세 |
|----------|------|------|
| 조성 (Key) | OMR 공유 | 조성기호(올림표/내림표) 개수 → 키 규칙 테이블 |
| 박자 (Time sig) | OMR 공유 | 숫자 심볼 검출 + 분수 조합 |
| 제목 | PaddleOCR | 제목 영역 OCR |
| 빠르기말 | PaddleOCR | 보표 상단 텍스트 (Andante, 보통 빠르게 등) |
| BPM | PaddleOCR + 정규식 | `♩\s*=\s*(\d+)` 패턴 매칭 |

Module 2와 YOLOv8 모델 **공유** → 클래스 목록에 key_sig_flat, key_sig_sharp, time_sig_num 추가.

---

### Module 4 — 가사 OCR

**모델:** PaddleOCR (한국어) → 찬송가 가사 파인튜닝

**도전 과제:**
- 음절 단위 분절 (각 음표마다 1음절)
- 여러 절이 수직으로 적층
- 악보 줄기/보와 겹침 가능
- 작은 폰트 (9~11pt)

**처리 흐름:**

```
가사 영역 (Module 1 출력)
     ↓ 수평 라인 분리 → 각 절(verse) 추출
     ↓ PaddleOCR 라인 단위 인식
절별 텍스트: ["저높고 푸른 하늘과", "주님의 크신 사랑을", ...]
     ↓ 음절 분리 (자모 단위)
음절 목록: ["저", "높", "고", "푸", "른", "하", "늘", "과", ...]
     ↓ 음표 개수와 매핑 (Module 2 결과 연동)
(음표, 음절) 쌍
```

**학습 데이터:** 실제 찬송가 스캔 + GT 가사 텍스트 (직접 제공)

**95% 달성 기준:** CER(문자 오류율) ≤ 5%

---

### Module 5 — MusicXML 조립

`music21` 스트림 API로 조립.

```python
score = music21.stream.Score()

# 메타 헤더
score.insert(0, music21.metadata.Metadata(title=meta.title))
score.insert(0, music21.tempo.MetronomeMark(number=meta.bpm))

# 성부별 파트
for voice in [SATB]:
    part = music21.stream.Part()
    part.insert(0, key_signature)
    part.insert(0, time_signature)
    for note, syllables in zip(notes[voice], lyrics_per_voice[voice]):
        n = music21.note.Note(note.pitch, quarterLength=note.duration)
        for verse_num, syllable in enumerate(syllables, 1):
            n.addLyric(syllable, lyricNumber=verse_num)
        part.append(n)
    score.append(part)

score.write('musicxml', fp=output_path)
```

---

## 4. 학습 데이터 전략

### 4.1 태스크별 데이터 전략

| 태스크 | 데이터 종류 | 획득 방법 | 목표 규모 |
|--------|-----------|---------|---------|
| **피치 (계이름)** | 실제 스캔 + GT 계이름 | 직접 제공 (레이블링) | 1,000장+ |
| **박자** | 합성 이미지 + 자동 레이블 | MusicXML → Lilypond 렌더링 | 5,000장+ |
| **가사** | 실제 스캔 + GT 가사 텍스트 | 직접 제공 (찬송가 가사집) | 500곡+ |
| **레이아웃** | 합성 + 자동 레이블 | 렌더링 시 영역 자동 추출 | 2,000장+ |

### 4.2 합성 데이터 생성 파이프라인

```
MusicXML (CPDL ~3,000곡 / MuseScore 찬송가)
     ↓ music21 → Lilypond 변환
     ↓ Lilypond 렌더링 (PNG, 150~400 DPI)
     ↓ 자동 레이블 추출 (MusicXML 좌표 역매핑)
(이미지, 음표 바운딩박스, 피치, 박자) 학습 쌍
```

**증강 전략:**
- 해상도: 150 / 200 / 300 / 400 DPI
- 가우시안 노이즈 (스캔 품질 시뮬레이션)
- 기울기 ±5°
- 밝기/대비 ±20%
- Lilypond 폰트 3종 (Emmentaler, Gonville, Bravura)

### 4.3 MusicXML 데이터 소스

| 소스 | 종류 | 규모 | 비고 |
|------|------|------|------|
| **CPDL** (Choral Public Domain Library) | 합창 MusicXML | ~3,000곡 | 공개 다운로드 |
| **MuseScore** 찬송가 | 찬송가 MusicXML | 수백 곡 | 이용약관 확인 |
| **한국 찬송가 직접 스캔** | 이미지 + GT 레이블 | 645장 | 핵심 평가 세트 |
| **교정 누적 (L4)** | 사용자 교정 | 점진적 증가 | AIScore 플라이휠 |

---

## 5. 평가 체계

### 5.1 음표 단위 (Note-level)

```python
# 정답 MusicXML vs 검출 MusicXML 비교
TP = 피치+박자+성부 모두 일치한 음표
FP = 검출됐지만 정답 없는 음표 (삽입 오류)
FN = 정답이지만 미검출 음표 (누락)

Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * P * R / (P + R)
```

### 5.2 기준선 vs 목표

| 지표 | Audiveris 기준 | Phase 1 목표 |
|------|--------------|------------|
| 소프라노 검출 Recall | 65% (34/52) | ≥ 95% |
| 마디 전체 누락 | 4/20마디 | 0 |
| 피치 정확도 | ~70% (추정) | ≥ 95% |
| 박자 정확도 | 미측정 | ≥ 95% |
| 가사 CER | 없음 (미구현) | ≤ 5% |

### 5.3 평가 데이터셋

- **개발 세트:** 한국 찬송가 50장 (GT MusicXML 포함)
- **테스트 세트:** 한국 찬송가 30장 + 1부 찬양 20장 (별도 보관)
- **기준 악보:** 315장 (소프라노 52음 GT 확보, 기존 비교 기준)

---

## 6. 단계별 개발 계획

### Phase 1 — 찬송가 SATB + 1부 찬양 (우선)

```
Step 0: 인프라 (1주)
  - Lilypond 설치 + 렌더링 스크립트
  - CPDL 찬송가 MusicXML 수집 (목표 300곡)
  - 합성 데이터 생성 파이프라인 구축

Step 1: 레이아웃 분석 (1주)
  - 투영 프로파일 기반 영역 분리
  - 찬송가 50장으로 검증

Step 2: OMR - 피치 (2~3주)
  - YOLOv8n DeepScores V2 사전학습 가중치 로드
  - 찬송가 합성 데이터 파인튜닝 (음표머리/기호)
  - 보표선 검출 + 피치 변환
  - 검출 Recall ≥ 90% 달성 확인 후 다음 단계

Step 3: OMR - 박자 (2주)
  - 음표 형태 분류기 (합성 데이터 학습)
  - 시각적 규칙 보완 레이어
  - 박자 정확도 ≥ 90% 달성

Step 4: 가사 OCR (2주)
  - PaddleOCR 한국어 모델 로드
  - 찬송가 가사 파인튜닝 (GT 직접 제공 데이터)
  - 절별 분리 + 음절 추출
  - CER ≤ 5% 달성

Step 5: 메타 추출 + MusicXML 조립 (1주)
  - 조성/박자 기호 검출 통합
  - PaddleOCR 제목/빠르기말
  - music21 MusicXML 조립기
  - E2E 검증: 315장 → MusicXML → 합창 WAV

Step 6: 95% 미달 항목 집중 개선 (2주)
  - 모듈별 오류 분석 → 약한 모듈 집중 튜닝
  - 교정 플라이휠(L4) 연결
```

### Phase 2 — 칸타타 PDF (후속)

```
Step 7: PDF 입력 처리
  - pdf2image 통합 (Module 0 확장)
  - 다중 페이지 → 시스템 단위 분할

Step 8: 레이아웃 분석 확장
  - YOLOv8 레이아웃 검출기 (오케스트라 스코어)
  - 파트 레이블 OCR (Soprano, Alto, Violin I ...)
  - 파트 선택 UI/API

Step 9: 멀티 인스트루먼트 OMR
  - 악기별 기보법 처리 (전위 기보 등)
  - SMT++ 파인튜닝 (오케스트라 데이터)
```

---

## 7. 프로젝트 디렉터리 구조

```
training/
├── data/
│   ├── raw/              # 원본 MusicXML, PDF
│   ├── rendered/         # Lilypond 렌더링 이미지
│   ├── annotations/      # YOLO 포맷 레이블
│   └── scanned/          # 실제 스캔 이미지 + GT
├── scripts/
│   ├── render_scores.py  # MusicXML → PNG (Lilypond)
│   ├── generate_labels.py# MusicXML → YOLO 바운딩박스 레이블
│   ├── augment.py        # 증강 파이프라인
│   └── evaluate.py       # 검출률 / 피치 / 박자 / CER 측정
├── models/
│   ├── layout/           # 레이아웃 분석 모델
│   ├── omr/              # YOLOv8 음악 기호 검출
│   └── ocr/              # PaddleOCR 찬송가 파인튜닝
└── notebooks/
    └── error_analysis.ipynb

backend/app/stages/omr/
├── score_understanding_adapter.py  # OmrPort 구현 (신규)
├── layout_analyzer.py
├── omr_engine.py
├── meta_extractor.py
├── lyrics_ocr.py
└── musicxml_assembler.py
```

---

## 8. 의존성

```yaml
# aiscore_env.yml 추가 예정
dependencies:
  - ultralytics        # YOLOv8 (pip)
  - paddlepaddle       # PaddleOCR 백엔드 (pip)
  - paddleocr          # 한국어 OCR (pip)
  - pdf2image          # PDF 처리 (pip, poppler 필요)
  - lilypond           # 악보 렌더링 (brew)
  - opencv-python      # 전처리 (이미 있음)
  - music21            # MusicXML 조립 (이미 있음)
```

---

## 9. 기술 선택 근거

### YOLOv8 선택
- PyTorch 기반 → 기존 `torch/MPS` 환경 그대로 사용
- DeepScores V2 음악 기호 검출 선례 존재
- Apple Silicon MPS 지원
- 파인튜닝 생태계 성숙

### PaddleOCR 선택
- 한국어 인식 모델 공개 제공
- 행 단위 인식 → 절별 가사 추출에 적합
- 로컬 실행 (외부 전송 없음, §16 규칙 준수)
- 파인튜닝 API 제공

### 합성 데이터 우선 전략
- 찬송가 스캔 이미지에 박자 레이블 수동 작업 불필요
- MusicXML → Lilypond → PNG 파이프라인으로 무제한 생성
- 증강으로 다양한 스캔 품질 시뮬레이션

### 헥사고날 어댑터 유지
- `OmrPort.recognize()` 인터페이스 불변
- OMR 엔진 교체(YOLOv8 → SMT++ → E2E)가 오케스트레이터 변경 없이 가능
- Phase 2 확장도 어댑터 파일만 추가

---

## 10. 참고 문헌

- **DeepScores V2**: 음악 기호 오브젝트 디텍션 데이터셋 (21 클래스)
- **SMT/SMT++**: End-to-End 폴리포닉 OMR 트랜스포머 (2023)
- **PaddleOCR**: 한국어 포함 80개 언어 OCR
- **CPDL**: Choral Public Domain Library (합창 MusicXML 3,000곡+)
- **Lilypond**: 오픈소스 악보 렌더링 엔진
- [DL-OMR 설계](./2026-06-19-dl-omr-design.md): 이전 OMR 특화 설계 문서
