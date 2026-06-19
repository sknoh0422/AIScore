# AIScore — 프로젝트 구조 설명서

> 이 문서는 AIScore 백엔드 아키텍처, 파이프라인, 구현 이력을 HTML 설명자료 제작을 위해 정리한 참고 문서입니다.
> 최종 갱신: 2026-06-19 (4차)

---

## 1. 프로젝트 개요

**AIScore**는 SATB(4성부 찬송가) 악보 이미지를 업로드하면,
악보를 자동 인식하고 각 성부를 AI 목소리로 합창시켜 **WAV 음원**을 생성하는 웹 서비스입니다.

### 핵심 파이프라인
```
악보 이미지 (카메라 촬영 / 파일 업로드)
    ↓ OMR (광학 악보 인식 — Audiveris)
  MusicXML
    ↓ 파싱 (music21 — chord→S/A/T/B 분리)
  Score (SATB 성부 분리)
    ↓ SVS (성부별 가창 합성) ×4 병렬
  성부별 WAV ×4  +  timing.json (음표 시작/종료 시각)
    ↓ 믹싱 (선택 성부만)
  [선택 성부] WAV ▶  +  악보 실시간 하이라이팅
```

### 단계 로드맵
| 단계 | 내용 | 상태 |
|------|------|------|
| **1단계** | 가사 무시, 모음 "우"로 합창 → 연습 가이드 트랙 | ✅ 완료 |
| **모바일** | iOS/Android 앱 — 파트 선택 재생 + 악보 싱크 하이라이팅 | 🔨 진행 중 |
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
| `OmrPort` | `AudiverisAdapter` | **DL-OMR 어댑터** (딥러닝, 찬송가 지도학습) |
| `ScoreParserPort` | `Music21Parser` | — |
| `SvsPort` | `VowelSynthAdapter` (포먼트+성악가 특성) | `LyricSingingAdapter` (2단계) |
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
├── frontend/                        # Next.js 웹 앱 (업로드·폴링·OSMD·오디오)
├── mobile/                          # React Native + Expo 모바일 앱 (진행 중)
│   ├── app/
│   │   ├── index.tsx                # HomeScreen (악보 촬영/선택/업로드)
│   │   ├── processing/[id].tsx      # ProcessingScreen (단계 폴링)
│   │   └── player/[id].tsx          # PlayerScreen (악보+파트선택+동기재생)
│   ├── components/
│   │   ├── PartSelector.tsx         # S/A/T/B 파트 토글
│   │   ├── AudioMixer.tsx           # expo-av 4성부 멀티트랙
│   │   ├── ScoreViewer.tsx          # WebView + OSMD + 하이라이팅
│   │   └── PlaybackControls.tsx     # 재생/정지/시크바
│   ├── lib/
│   │   ├── api.ts                   # FastAPI 클라이언트
│   │   └── timing.ts                # 음표 타이밍 계산 유틸
│   └── assets/score-viewer.html     # WebView OSMD 호스트 페이지
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
               → voice_paths = {soprano/alto/tenor/bass: WAV경로}
               → timing_path = timing.json (음표별 시작/종료 초)
        → mixing  (Mixer 합창 합성)
          → done   ✅  result_path = choir.wav
          ↘ failed ❌  failed_stage + error 메시지 기록
```

**잡 결과 필드:**
| 필드 | 설명 |
|------|------|
| `result_path` | 전체 합창 WAV |
| `score_path` | MusicXML (OSMD 렌더링용) |
| `voice_paths` | 성부별 WAV `{soprano, alto, tenor, bass}` |
| `timing_path` | 음표 타이밍 JSON (모바일 하이라이팅용) |

어느 단계에서 예외가 발생해도 잡 상태가 `failed`로 즉시 표면화됩니다 (조용한 실패 금지).

---

## 5. OMR 엔진 비교 및 진단

### 엔진 비교

| 엔진 | 특징 | 결론 |
|------|------|------|
| **oemer** | 빠름, 단성부 전용(2-track 가정) | 밀집형 SATB 크래시 → 단성부 전용 강등 |
| **Audiveris** | OSS/Java, 로컬, MusicXML, SATB 지원 | 채택했으나 정확도 한계 — DL로 교체 예정 |
| SMT/SMT++ | 트랜스포머 폴리포닉, 고천장 | 차세대 DL-OMR 후보 |
| 상용(PlayScore 등) | 정확도 높음 | 외부 전송(규칙 §16 위반) → 자동 제외 |
| **DL-OMR (자체)** | 찬송가 특화, 지도학습, 로컬 | **개발 예정** — 설계 문서 참조 |

**핵심 발견:** 원본 500×777px 이미지는 Audiveris도 실패 (interline 6px).  
→ **3× LANCZOS 업스케일 전처리** 후 OMR 성공. `preprocess.py`가 자동 처리.

### Audiveris 정확도 실측 결과 (2026-06-19)

찬송가 315장 소프라노 파트 기준 심층 진단:

| 항목 | 수치 |
|------|------|
| 정답 음표 수 | 52음 |
| 검출 음표 수 | 34음 |
| **검출률** | **65%** |
| 전체 누락 마디 | m1, m6, m11, m16 (4개 — 각 악절 첫 마디) |
| 피치 오인식 | m2(D5→정답A), m3(G5→정답Bb) 등 다수 |

**Audiveris MXL 파트 구조:**
```
Part 0 (Voice / 트레블): 소프라노+알토 혼합
  → 마디별로 Voice1/Voice2 혼재 (불규칙)
  → 일부 마디는 flat notesAndRests, 일부는 Voice 구조
Part 1 (Voice / 베이스): 테너+베이스 혼합
```

**근본 원인:** Audiveris가 각 악절 시작 마디의 음표를 완전히 미인식.  
파서 수정으로는 해결 불가 → **DL 기반 OMR 재개발 결정**.

→ 설계 문서: [`docs/superpowers/specs/2026-06-19-dl-omr-design.md`](superpowers/specs/2026-06-19-dl-omr-design.md)

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
| 환경 | conda `aiscore` · Apple Silicon(MPS→CPU fallback) |
| OMR | Audiveris 5.10.2 (Java/JDK25) |
| 악보 파싱 | music21 |
| 가창 합성 | 자체 VowelSynth — 성악가 특성 모델링 (포먼트 필터 + 성부별 비브라토 rate/depth + squillo) |
| 오디오 | soundfile · numpy |
| 이미지 전처리 | Pillow (LANCZOS 3× 업스케일) |
| 테스트 | pytest · TestClient |
| 웹 프론트엔드 | Next.js 15 · Tailwind v4 · TypeScript 5 · OSMD |
| **모바일 앱** | **React Native · Expo SDK 51 · expo-av · expo-image-picker · react-native-webview** |
| 악보 렌더링 | OSMD (OpenSheetMusicDisplay) — 웹/WebView 공통 |
| 버전 관리 | Git / GitHub (`sknoh0422/AIScore`) |

---

## 8. 구현 이력 (전체)

| 날짜 | 작업 | 산출물 |
|------|------|--------|
| 2026-06-16 | 프로젝트 설계 · 헥사고날 아키텍처 확정 | `docs/superpowers/specs/`, `CLAUDE.md` |
| 2026-06-16 | 빈 스캐폴딩 + `ports.py` 동결 | 디렉터리 구조, `domain/ports.py` |
| 2026-06-16~17 | **1단계 파이프라인** TDD 구현 | 16 tests, `feat/stage1-vowel-choir` → main |
| 2026-06-17 | OMR 실측 검증 — oemer SATB 크래시 확인 | oemer 한계 발견, Audiveris 필요성 확정 |
| 2026-06-17 | **Audiveris OMR** 빌드·실측·TDD 구현 | 24 tests, E2E 18s WAV, `feat/audiveris-omr` → main |
| 2026-06-18 | **품질 개선 5종** | 33 tests, `feat/quality-improvements` → main |
| 2026-06-18 | **웹 프론트엔드** (Next.js + OSMD) | 업로드·폴링·악보렌더·오디오, `feat/frontend` → main |
| 2026-06-18 | **성악 품질 개선** (4성부 분리, 포먼트+비브라토) | `feat/vocal-quality` → main |
| 2026-06-18 | **악보 메타 API + 웹 UI 개선** | `/meta` `/image` 엔드포인트, 성부별 플레이어, 악보+음표 비교 뷰 |
| 2026-06-18 | **모바일 앱 설계** (React Native + Expo) | 계획서 11 Tasks 작성 완료 |
| 2026-06-19 | **OMR 심층 진단** — MXL 파트 구조 분석 | 315장 소프라노 65% 정확도, 4마디 전체 누락 확인 |
| 2026-06-19 | **DL-OMR 재설계 방향 확정** | 설계 문서 `2026-06-19-dl-omr-design.md` |

## 9. 모바일 앱 아키텍처

```
[iPhone / Android]
  ┌─────────────────────────┐
  │  HomeScreen             │  expo-image-picker (촬영/갤러리)
  │  ProcessingScreen       │  2초 폴링 → 단계 진행 표시
  │  PlayerScreen           │
  │  ├─ ScoreViewer         │  WebView + OSMD + postMessage 하이라이팅
  │  ├─ PartSelector        │  S/A/T/B 토글 (복수 선택)
  │  ├─ AudioMixer          │  expo-av 4성부 멀티트랙 (GainNode on/off)
  │  └─ PlaybackControls    │  재생/정지/시크바
  └─────────────────────────┘
          ↕ HTTP
  [FastAPI 백엔드]
    GET /jobs/{id}/audio/{voice}   성부별 WAV
    GET /jobs/{id}/timing          음표 타이밍 JSON
    GET /jobs/{id}/score           MusicXML
```

**타이밍 동기화 흐름:**
```
AudioMixer.currentTime (100ms 폴링)
  → findNoteIndex(timingData, currentTime)
  → ScoreViewer.postMessage({type:"seek", currentTime})
  → WebView JS: OSMD cursor.next() × N + 색상 변경
```
