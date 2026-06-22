# AIScore — AI 기반 찬송가 악보 합창 서비스 설계 문서

- **작성일:** 2026-06-16
- **상태:** 설계 확정 (구현 전)
- **작업 디렉터리:** `/Users/sknoh/Documents/Workspace/aiscore`

---

## 1. 제품 정의

사용자가 **4성부 찬송가 악보(SATB) 이미지**를 업로드하면 → 기계가 악보를 읽어 디지털 데이터로 변환하고 → **각 성부(S·A·T·B)를 AI 목소리로 노래시켜** → 4개를 합쳐 **AI 찬양대 합창 음원**을 돌려주는 웹 기반 크로스플랫폼 서비스.

- **핵심 가치:** 단순 MIDI 재생이 아니라 "가사를 부르는 목소리" 합성. 따라서 음표뿐 아니라 **가사–음표 매핑**이 핵심 과제.
- **난점:** 밀집형 SATB 악보(한 보표에 두 성부 겹침)의 고정밀 인식, 한글 가사 처리.
- **타깃 플랫폼:** Web (Mac/Windows/iOS/Android 브라우저).

---

## 2. 단계 로드맵 (난이도 사다리)

가장 어려운 두 조각(한글 가사 OCR, 한국어 가창 SVS)을 우회하기 위해 단계적으로 진행한다.

| 단계 | 입력 | 핵심 기술 | 리스크 |
|---|---|---|---|
| **1단계** | 음표만 (가사 무시) | OMR(음표) + music21 + **모음 "우" 합성** + 믹싱 | 낮음 — 전 구간 성숙 기술 |
| **2단계** | 음표 + 가사 | + 가사 소스(텍스트입력 기본/OCR 보조) + 정렬 + **가사 가창 SVS** | 높음 — 본격 R&D |

- **1단계 결과물:** 성부별 "우~" 합창 = 연습용 가이드 트랙. 위험 요소가 거의 없는 성숙 기술만 사용.
- **2단계 가사 소스 3단계 신뢰도:** ① 텍스트 직접 입력→음절 자동 정렬(기본, 항상 동작) ② OCR 자동 추출(보조, 가변) ③ 에디터 수동 배정(최종 정답). → OCR 정확도가 부족해도 제품은 무너지지 않는다(OCR은 필수가 아닌 선택).
- **트랙 B (오프라인 R&D):** 교정 데이터(L4)를 모아 한글 OCR 지도학습 → (장기) 커스텀 OMR. 학습 모델은 어댑터로 끼움(`CustomKoreanOcrAdapter` 등). 서빙 경로와 분리.

### 기술 타당성 결론
- "악보를 읽고 이해" = ① 음표 인식(oemer, 실용적) + ② 가사 텍스트 추출(가장 약한 고리) + ③ 가사–음표 정렬(①②되면 풀림)로 분리됨.
- 가사는 OMR로 뽑지 않는다. 가사 추출을 OMR과 분리해 별도 가사 소스(텍스트 입력 우선, OCR 보조)로 처리.
- SVS는 성숙 기술이나 한국어 g2p·voicebank·SATB 4음역 부담이 큼 → 1단계 모음 "우" 합성으로 우회.

---

## 3. 레이어 구조 (런타임 아키텍처)

**설계 원칙: 포트&어댑터(헥사고날).** 핵심 도메인은 프레임워크/모델에 무관, 바깥(API)→안(도메인) 단방향 의존. 교체 가능한 부분(OMR/가사/SVS)은 전부 어댑터.

```
Frontend (Next.js + OSMD): 업로드 · MusicXML 렌더 · 교정 에디터 · 재생/다운로드
        │ HTTP (REST, 비동기 잡)
        ▼
L1 API/Gateway (FastAPI)   엔드포인트 · Pydantic 스키마 · 잡 생성/상태/결과
L2 Orchestration           파이프라인 잡 모델 · 단계 조율 · 4성부 병렬 · 진행상태
L3 Pipeline Stages (각 단계 = 인터페이스 + 어댑터)
     OMR(img→MusicXML) │ LyricSource │ ScoreModel(music21) │ LyricAligner │ SVS │ Mixing
     ▸Oemer(1차)        │ ▸TextInput  │ SATB 성부분리        │ slur/tie/절  │ ▸Vowel"우" │
     ▸Audiveris(자리)   │ ▸OCR(보조)  │ 내부 Score 모델      │ [2단계]      │ ▸Lyric(자리)│
                        │ [2단계]     │                      │              │ [2단계]     │
L4 Correction/Dataset      교정 결과를 (이미지,정답) 라벨로 저장 → 플라이휠 [1단계부터]
L5 Storage                 업로드/중간산출(MusicXML)/성부 WAV/결과물 · 잡 메타데이터

(오프라인, 요청경로 밖)
R1 Training (offline R&D)  데이터셋 → 한글 OCR 지도학습 → 모델 산출  [자리만, 비움]

횡단 관심사: Config(디바이스/모델경로) · Logging · Error/도메인 예외
```

### 레이어 핵심 규칙
1. **의존성 방향:** L1→L2→L3, L3는 추상(인터페이스)에만 의존. ScoreModel(도메인)은 FastAPI/torch를 모름.
2. **교체점은 어댑터뿐:** OMR/LyricSource/SVS는 인터페이스 뒤. "자리" = 비워두는 미래 어댑터.
3. **단계 토글:** `[2단계]` 레이어는 1단계엔 비활성, 인터페이스 경계만 존재.
4. 1단계 = `OMR(음표) → ScoreModel → SVS(Vowel "우") → Mixing`. 2단계 = LyricSource/Aligner 켜고 SVS 어댑터 교체 → 리라이트 0.

### L4 상세 (교정 = 무료 라벨링)
사용자가 에디터에서 OMR/OCR 오류를 고치는 순간이 "기계의 오답"과 "사람의 정답"을 동시에 아는 유일한 순간. 이를 `(잘라낸 이미지 영역, 기계가_읽은값, 사람이_고친값, 시각)` 한 줄로 저장. 1단계에서는 단순 append 로깅(ML 아님, 백그라운드, 사용자 지연 없음). 데이터는 지나가면 못 줍기에 1단계부터 수집한다. 원본과 분리 저장, 개인식별자 미포함.

---

## 4. 데이터 흐름

OMR(1~2분)·SVS가 느려 동기 응답 불가 → 비동기 잡 모델.

### 1단계 흐름 (모음 "우")
```
업로드 → L1: 잡 생성·이미지 저장(L5)·job_id 반환 → (백그라운드 L2)
  ① OMR(Oemer):        이미지 → MusicXML(음표)        status="omr"
  ② ScoreModel(music21): MusicXML → 내부 Score, SATB 분리 (1단계 가사 스킵) status="parsing"
  ③ SVS (★4성부 병렬★): S/A/T/B 각각 Vowel"우" → 4 WAV   status="synth"
  ④ Mixing:            4 WAV → choir.wav 저장(L5)        status="done"
→ 프론트: OSMD 렌더 + choir.wav 재생/다운로드
```

### 교정 루프 (선택, 1단계부터)
```
에디터 음표 수정 → PATCH /jobs/{id}/score
  ├─ L4: (이미지영역, 오답, 정답) 라벨 저장
  └─ Score 갱신 → ③④ 재실행 → 새 choir.wav
```

### 2단계 추가 구간 (② 와 ③ 사이 삽입)
```
② ScoreModel → ②' LyricSource(TextInput 기본/OCR 보조) → ②'' LyricAligner(음절↔음표, slur/tie/절) → ③ SVS(LyricSinging)
가사 교정도 → L4 저장 (동일 경로)
```
1단계→2단계 차이 = 점선 구간 삽입 + ③ 어댑터 교체뿐. L1/L2/④ 흐름 불변.

### 잡 상태 모델
```
queued → omr → parsing → [lyric → align] → synth → mixing → done
                                                          ↘ failed (단계+원인 기록)
```

### 데이터 흐름 포인트
- **병렬은 ③ SVS만** (4성부 독립). OMR/믹싱은 순차.
- 각 단계 산출물(MusicXML, 성부 WAV)을 L5 저장 → 실패 시 그 단계부터 재시작, 교정 후 ③만 재실행 가능.
- 상태는 단계 이름으로 노출 → 프론트 진행률 표시.

---

## 5. 디렉터리 구조 / 스캐폴딩

모노레포 1개(backend / frontend / training). 디렉터리가 곧 레이어 경계. 초기 스캐폴딩은 빈 스텁(docstring + 인터페이스).

```
aiscore/
├── CLAUDE.md
├── README.md
├── aiscore_env.yml                # 기존 유지
├── .gitignore                     # data/, 모델, 대용량 오디오 제외
├── docs/superpowers/specs/2026-06-16-aiscore-design.md
├── score_images/                  # 기존 샘플 (315.JPG, 온맘다해.png)
├── notebooks/main.ipynb           # 기존 노트북 이동(스파이크/참고)
│
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI 진입
│   │   ├── api/                   # L1
│   │   │   ├── routes/jobs.py
│   │   │   └── schemas.py
│   │   ├── orchestration/         # L2
│   │   │   ├── orchestrator.py
│   │   │   └── job.py
│   │   ├── domain/                # 순수 도메인 (프레임워크 무관)
│   │   │   ├── score.py           # 내부 Score(S/A/T/B·note·lyric)
│   │   │   └── ports.py           # OmrPort/LyricSourcePort/AlignerPort/SvsPort/MixerPort
│   │   ├── stages/                # L3 어댑터(포트 구현)
│   │   │   ├── omr/oemer_adapter.py
│   │   │   ├── omr/audiveris_adapter.py        # 자리
│   │   │   ├── parsing/music21_parser.py
│   │   │   ├── lyrics/text_input_provider.py   # 2단계
│   │   │   ├── lyrics/ocr_provider.py          # 2단계·자리
│   │   │   ├── lyrics/aligner.py               # 2단계
│   │   │   ├── svs/vowel_synth_adapter.py      # 1단계 "우"
│   │   │   ├── svs/lyric_singing_adapter.py    # 2단계·자리
│   │   │   └── mixing/mixer.py
│   │   ├── corrections/recorder.py # L4
│   │   ├── storage/store.py        # L5
│   │   └── core/                   # 횡단
│   │       ├── config.py
│   │       ├── device.py           # mps→cuda→cpu 선택
│   │       └── errors.py
│   └── tests/
│
├── frontend/                       # Next.js
│   ├── app/                        # 업로드 · 잡 상태 · 교정 에디터(OSMD)
│   ├── components/
│   └── lib/api.ts
│
├── training/                       # R1 오프라인 (비움)
│   ├── datasets/
│   ├── ocr/
│   └── README.md
│
└── data/                           # 런타임 산출물 (gitignore)
    ├── uploads/  jobs/  results/
    └── corrections/                # L4 라벨 저장소
```

### 스캐폴딩 원칙
- `domain/`(score.py, ports.py)은 순수 Python — torch/fastapi/music21 import 금지.
- 교체점은 전부 `stages/` 안. "자리" = 빈 미래 어댑터.
- `data/`·모델·대용량 WAV는 git 추적 제외.
- 기존 `main.ipynb`는 `notebooks/`로 이동 보존.

---

## 6. 개발시간 에이전트 오케스트레이션

> 앱 런타임이 아니라 "이 프로젝트를 Claude Code로 개발/유지하는 방식". (이중 정의 중 개발시간)

### 오케스트레이터
메인 세션이 오케스트레이터. 계획 수립 · 작업을 전문 에이전트로 라우팅 · 인터페이스(`ports.py`) 동결 · 리뷰 게이트 통과 확인. 원칙: **인터페이스 먼저 동결 → 구현 분배 → 리뷰 게이트.**

### 에이전트 로스터 (레이어 → 담당 / 리뷰)
| 레이어/작업 | 구현·해결 | 리뷰 게이트 |
|---|---|---|
| 설계·계획 | `ecc:architect`, `Plan`, `superpowers:writing-plans` | — |
| 코드 탐색 | `Explore`, `ecc:code-explorer` | — |
| L1/L2/L4/L5 (Python·FastAPI) | 메인/`general-purpose` + `superpowers:TDD` | `ecc:fastapi-reviewer`, `ecc:python-reviewer` |
| L3 SVS/믹싱 (torch·오디오) | 메인 + `ecc:pytorch-build-resolver` | `ecc:python-reviewer`, `ecc:performance-optimizer` |
| L3 OMR/파싱/정렬 | 메인 + `superpowers:TDD` | `ecc:python-reviewer` |
| Frontend (Next.js/React/TS) | 메인/`general-purpose` | `ecc:react-reviewer`, `ecc:typescript-reviewer`; 빌드 `ecc:react-build-resolver` |
| 트랙 B 학습 (`training/`) | `ecc:pytorch-build-resolver`, `ecc:mle-reviewer` | `ecc:mle-reviewer` |
| 보안 (업로드·엔드포인트) | — | `ecc:security-reviewer` (외부입력 변경 시 필수) |
| 디버깅 | `superpowers:systematic-debugging` | — |
| 모든 코드 변경 | — | `ecc:code-reviewer` + `superpowers:requesting-code-review` (머지 전 필수) |

### 라우팅 규칙 (파일 경로 → 리뷰 에이전트)
```
backend/app/api|orchestration|storage|corrections/**  → python-reviewer + fastapi-reviewer
backend/app/stages/svs|mixing/**                       → python-reviewer + performance-optimizer (+pytorch-build-resolver)
backend/app/stages/omr|parsing|lyrics/**               → python-reviewer
backend/app/domain/**                                  → python-reviewer + type-design-analyzer
frontend/**                                            → react-reviewer + typescript-reviewer
training/**                                            → mle-reviewer
* (파일 업로드/외부입력 경로 포함)                      → + security-reviewer
```

### 병렬화 원칙
1. **인터페이스 동결이 선결.** `domain/ports.py` 확정 전 stage 구현 병렬 금지.
2. 동결 후 독립 모듈은 병렬 가능 (omr_adapter ∥ mixer ∥ storage).
3. frontend ↔ backend 는 API 스키마(`schemas.py`) 합의 후 병렬.
4. 공유 파일 동시 수정 작업은 병렬 금지(또는 git worktree 격리).
5. 리뷰는 다음 구현과 병렬 진행.
6. **수직 슬라이스 우선** — 1단계 경로를 먼저 끝까지 동작시키고 폭 확장.

### 절대적 순서
```
계획 → 인터페이스 동결(ports.py) → TDD 구현 → 리뷰 게이트 → 검증 → 통합
```

---

## 7. 절대 규칙 (가드레일)

### A. 환경·도구
1. 모든 Python 실행은 conda 환경 `aiscore`(py3.10) 안에서. `aiscore_env.yml`이 기준이나, **의존성 해석기에 따라 파이썬/전이 라이브러리 버전 자동 조정 허용** — 엄격한 핀 고정으로 싸우지 않고, 직접(top-level) 의존성만 명시 기록.
2. **개발·검증은 macOS(Apple Silicon, MPS)** 에서. 단 **다중 OS 이식성을 설계 목표로** — OS 종속 가정 금지, 경로는 `pathlib` 중립, 디바이스 선택은 `core/device.py` 한 곳에서 `mps → cuda → cpu` 우선순위로 추상화.
3. Bash 첫 명령 시 Fact-Forcing 게이트 준수.

### B. 아키텍처 규율
4. 의존성 단방향: api→orchestration→domain. `domain/`에 torch·fastapi·music21 import 금지(순수 Python).
5. 교체점은 어댑터로만. 오케스트레이터/도메인은 구체 구현(oemer, DiffSinger…) 직접 import 금지 — `ports.py` 경유.
6. `ports.py` 동결 전 stage 구현 시작 금지.
7. 새 외부 모델/엔진 추가 = 기존 코드 수정이 아니라 새 어댑터 파일 추가로.

### C. 프로세스·품질
8. TDD: 구현 전 실패 테스트 먼저. 도메인·정렬·믹싱 로직은 단위테스트 필수.
9. 머지 전 리뷰 게이트 필수. 통과 없이 "완료" 선언 금지.
10. 검증 없는 완료 주장 금지 — 테스트/실행 출력으로 증명.
11. 버그·예외는 추측 수정 금지 → `superpowers:systematic-debugging`.
12. 조용한 실패 금지: OMR/SVS 단계 실패는 잡 상태 `failed`(단계+원인)로 표면화.

### D. 데이터·안전
13. 업로드 악보·생성 음원·교정 데이터는 사용자 자산. `data/`·모델·대용량 WAV는 git 커밋 금지(.gitignore).
14. 외부 입력(파일 업로드, 가사 텍스트) 경로 변경 시 `security-reviewer` 필수(경로 traversal·파일타입·크기 제한).
15. L4 교정 라벨은 원본과 분리 저장, 개인식별자 미포함.
16. 외부 전송/공개 동작(배포·업로드)은 명시 승인 전 금지.

### E. 단계·범위 규율
17. 1단계 스코프 고정: 음표→모음 "우"→믹싱. 가사 OCR/정렬/가창은 `[2단계]` 표식 유지, 1단계에 끌어오지 않음(YAGNI).
18. 수직 슬라이스 우선: end-to-end 한 줄 동작 후 폭 확장.
19. `training/`(트랙 B)는 서빙 요청 경로에 들이지 않음(오프라인 분리).
20. 응답·문서·주석은 한국어 기본.

---

## 8. 이번 세션 산출물

1. 본 설계 문서 (확정)
2. `CLAUDE.md` — 요약·이중 오케스트레이션·레이어·에이전트·라우팅·병렬화·절대규칙
3. 빈 스캐폴딩 — 위 디렉터리 구조의 스텁(인터페이스/docstring), 구현 로직 없음
