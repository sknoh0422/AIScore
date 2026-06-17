# AIScore — 프로젝트 구조 설명서

> 이 문서는 AIScore 백엔드 아키텍처, 파이프라인, 구현 이력을 HTML 설명자료 제작을 위해 정리한 참고 문서입니다.
> 최종 갱신: 2026-06-18

---

## 1. 프로젝트 개요

**AIScore**는 SATB(4성부 찬송가) 악보 이미지를 업로드하면,
악보를 자동 인식하고 각 성부를 AI 목소리로 합창시켜 **WAV 음원**을 생성하는 웹 서비스입니다.

### 핵심 파이프라인
```
악보 이미지
    ↓ OMR (광학 악보 인식)
  MusicXML
    ↓ 파싱 (music21)
  Score (SATB 성부 분리)
    ↓ SVS (성부별 가창 합성) ×4 병렬
  성부별 WAV ×N
    ↓ 믹싱
  합창 WAV ▶
```

### 단계 로드맵
| 단계 | 내용 | 상태 |
|------|------|------|
| **1단계** | 가사 무시, 모음 "우"로 합창 → 연습 가이드 트랙 | ✅ 완료 |
| **2단계** | 가사 추가(텍스트 입력/OCR) + 음절↔음표 정렬 + 가사 가창 | 예정 |
| **트랙 B** | 교정 데이터로 한글 OCR 지도학습(오프라인) | 예정 |

---

## 2. 아키텍처: 헥사고날(포트 & 어댑터)

의존성은 **바깥 → 안 단방향**입니다. 도메인은 외부 라이브러리에 의존하지 않습니다.

```
┌──────────────────────────────────────────────┐
│  L1  API / Gateway  (FastAPI 엔드포인트)       │
│       POST /jobs  ·  GET /jobs/{id}           │
└───────────────────┬──────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│  L2  Orchestration  (파이프라인 조율)          │
│       Stage1Orchestrator  ·  Job 상태 관리    │
└───────────────────┬──────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│  L3  Pipeline Stages  (어댑터 교체점)          │
│  OMR      : AudiverisAdapter (현재)           │
│             OemerAdapter     (단성부 전용)     │
│  Parsing  : Music21Parser                     │
│  SVS      : VowelSynthAdapter (1단계: "우")   │
│  Mixing   : Mixer                             │
└───────────────────┬──────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│  Domain  (순수 Python, 외부 의존 없음)         │
│   Score · Voice · Note · VoiceName            │
│   ports.py  (Protocol 인터페이스 정의)         │
└──────────────────────────────────────────────┘

  L4  Correction/Dataset  backend/app/corrections/
  L5  Storage             backend/app/storage/
  —   Core(횡단)          backend/app/core/  (config · device · errors)
  R1  Training(오프라인)  training/  (서빙 경로 밖)
```

### 교체점 (어댑터 패턴)
모든 외부 엔진은 `backend/app/stages/` 안에 어댑터로 격리됩니다.  
도메인과 오케스트레이터는 `ports.py`의 **Protocol(인터페이스)에만 의존**합니다.

| 포트 | 현재 어댑터 | 차후 교체 |
|------|-----------|---------|
| `OmrPort` | `AudiverisAdapter` | SMT/SMT++ (트랜스포머 폴리포닉) |
| `ScoreParserPort` | `Music21Parser` | — |
| `SvsPort` | `VowelSynthAdapter` | `LyricSingingAdapter` (2단계) |
| `MixerPort` | `Mixer` | — |
| `LyricSourcePort` | (2단계) | `TextInputProvider` / `OcrProvider` |

---

## 3. 파일 구조

```
aiscore/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/jobs.py       # POST /jobs, GET /jobs/{id}
│   │   │   └── schemas.py           # Pydantic 요청/응답 스키마
│   │   ├── core/
│   │   │   ├── config.py            # Audiveris/JDK 경로, OMR 파라미터
│   │   │   ├── device.py            # MPS→CUDA→CPU 디바이스 선택
│   │   │   └── errors.py            # PipelineError 계층 (OmrError, ParseError, …)
│   │   ├── domain/
│   │   │   ├── ports.py             # Protocol 인터페이스 (동결)
│   │   │   └── score.py             # Score, Voice, Note, VoiceName 도메인 모델
│   │   ├── orchestration/
│   │   │   ├── job.py               # Job, JobStatus (queued→…→done/failed)
│   │   │   └── orchestrator.py      # Stage1Orchestrator (SVS 4성부 병렬)
│   │   ├── stages/
│   │   │   ├── omr/
│   │   │   │   ├── audiveris_adapter.py  # Audiveris 배치 CLI 어댑터
│   │   │   │   ├── oemer_adapter.py      # oemer CLI 어댑터 (단성부)
│   │   │   │   └── preprocess.py         # 저해상도 이미지 업스케일
│   │   │   ├── parsing/
│   │   │   │   └── music21_parser.py     # MusicXML → Score (part×voice 매핑)
│   │   │   ├── svs/
│   │   │   │   ├── vowel_synth_adapter.py  # 모음 "우" 가창 합성
│   │   │   │   └── lyric_singing_adapter.py # [2단계 자리]
│   │   │   └── mixing/
│   │   │       └── mixer.py              # 성부별 WAV → 합창 WAV
│   │   ├── storage/
│   │   │   └── store.py             # 인메모리 JobStore + 파일 디렉터리
│   │   └── corrections/
│   │       └── recorder.py          # [L4] 교정 라벨 누적
│   ├── tests/
│   │   ├── conftest.py              # store 격리 autouse fixture
│   │   ├── test_ports.py            # 포트 계약 (isinstance) 테스트
│   │   ├── test_parser.py / test_parser_satb.py
│   │   ├── test_mixer.py
│   │   ├── test_orchestrator.py / test_orchestrator_nvoice.py
│   │   ├── test_audiveris_adapter.py
│   │   ├── test_api.py
│   │   └── … (총 33개 테스트, integration 마크 별도)
│   └── pyproject.toml
├── frontend/                        # Next.js (예정)
├── training/                        # 오프라인 OCR 학습 (트랙 B)
├── docs/
│   ├── ROADMAP.md                   # 세션 진입점 · 진행 상태
│   ├── ARCHITECTURE.md              # 이 문서
│   └── superpowers/
│       ├── specs/                   # 설계 문서
│       └── plans/                   # 단계별 구현 계획
└── CLAUDE.md                        # 프로젝트 헌법 (규약 20조)
```

---

## 4. 잡(Job) 상태 모델

```
queued
  → omr        (Audiveris 악보 인식)
    → parsing  (music21 SATB 분리)
      → synth  (VowelSynth 성부별 가창 ×N 병렬)
        → mixing  (Mixer 합창 합성)
          → done   ✅  result_path = "data/jobs/{id}/choir.wav"
          ↘ failed ❌  failed_stage + error 메시지 기록
```

어느 단계에서 예외가 발생해도 잡 상태가 `failed`로 즉시 표면화됩니다 (조용한 실패 금지).

---

## 5. OMR 엔진 선택 배경

| 엔진 | 특징 | 결론 |
|------|------|------|
| **oemer** | 빠름, 단성부 전용(2-track 가정) | 밀집형 SATB 크래시 → 단성부 전용 강등 |
| **Audiveris** | OSS/Java, 로컬, MusicXML, SATB 지원 | **채택** (저해상도 전처리 필수) |
| SMT/SMT++ | 트랜스포머 폴리포닉, 고천장 | 장기 백로그 |
| 상용(PlayScore 등) | 정확도 높음 | 외부 전송(규칙 위반) → 자동 제외 |

**핵심 발견:** 원본 500×777px 이미지는 Audiveris도 실패 (interline 6px).  
→ **3× LANCZOS 업스케일 전처리** 후 OMR 성공. `preprocess.py`가 자동 처리.

---

## 6. 구현 이력 요약

| 날짜 | 작업 | 산출물 |
|------|------|--------|
| 2026-06-16 | 프로젝트 설계 · 헥사고날 아키텍처 확정 | `docs/superpowers/specs/`, `CLAUDE.md` |
| 2026-06-16 | 빈 스캐폴딩 + `ports.py` 동결 | 디렉터리 구조, `domain/ports.py` |
| 2026-06-16~17 | **1단계 파이프라인** TDD 구현 | 16 tests, `feat/stage1-vowel-choir` → main |
| 2026-06-17 | OMR 실측 검증 — oemer SATB 크래시 확인 | oemer 한계 발견, Audiveris 필요성 확정 |
| 2026-06-17 | **Audiveris OMR** 빌드·실측·TDD 구현 | 24 tests, E2E 18s WAV, `feat/audiveris-omr` → main |
| 2026-06-18 | **품질 개선 5종** | 33 tests, `feat/quality-improvements` → main |

### 품질 개선 5종 상세 (2026-06-18)
1. **파서 0-파트 방어** — 빈 MusicXML → `ParseError` 명시 발생
2. **업로드 OOM 방어** — `file.read(_MAX_BYTES+1)`: 전체 읽기 전 크기 제한
3. **믹서 스테레오 처리** — `_to_mono()` + 입력 samplerate 사용 (44100 하드코딩 제거)
4. **테스트 Store 격리** — `JobStore.reset(root)` + `conftest.py` autouse fixture
5. **포트 계약 테스트** — `test_ports.py` 5개 어댑터 `isinstance` 계약 검증

---

## 7. 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 | Python 3.10 · FastAPI · uvicorn |
| 환경 | conda `aiscore` · Apple Silicon(MPS) |
| OMR | Audiveris 5.10.2 (Java/JDK25) |
| 악보 파싱 | music21 |
| 가창 합성 | 자체 VowelSynth (사인파 기반, 1단계) |
| 오디오 | soundfile · numpy |
| 이미지 전처리 | Pillow (LANCZOS 업스케일) |
| 테스트 | pytest · TestClient |
| 프론트엔드 | Next.js + OSMD (예정) |
| 버전 관리 | Git / GitHub (`sknoh0422/AIScore`) |

---

## 8. 다음 작업 (프론트엔드)

```
프론트엔드 (Next.js + OSMD)
  ├── 파일 업로드 UI          → POST /jobs
  ├── 잡 상태 폴링            → GET /jobs/{id}  (queued→done/failed)
  ├── 악보 렌더링              → OSMD (OpenSheetMusicDisplay)
  ├── 합창 WAV 재생            → HTML5 Audio
  └── 교정 에디터 (후속)       → SATB 성부 수동 수정
```
