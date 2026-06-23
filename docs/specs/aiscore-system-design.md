# AIScore 시스템 설계 — How 문서

> **작성일:** 2026-06-23  
> **역할:** 전체 시스템의 소스 구조·데이터 흐름·기능 구성 상세 (How).  
> **연계:** [ROADMAP.md](../ROADMAP.md) | [DL-OMR 설계 원칙](2026-06-19-dl-omr-design.md) | [CLAUDE.md](../../CLAUDE.md)

---

## 1. 개요

### 1.1 목적

찬송가 악보 이미지를 입력받아 4성부(SATB) 악보를 앱/웹 화면에 표시하고, 성부별 또는 전체 음성(SVS·MIDI)을 재생하는 서비스를 구현한다. 악보 인식(OMR) 모델은 보유한 645쌍의 이미지-MusicXML 데이터를 ground truth로 삼아 지도학습한다.

### 1.2 핵심 목표

| 목표 | 기준 |
|------|------|
| OMR 정확도 | 음표 인식률 ≥ 95% |
| 악보 표시 | SATB 4성부 렌더링 (OSMD) |
| 성부 재생 | 성부 선택 → SVS/MIDI 출력 |
| 악보 위치 동기화 | 재생 중 cursor 위치 표시 |
| 가사 (2단계) | OCR 추출 + 음절↔음표 정렬 |

### 1.3 최종 사용자 흐름

```
사용자
  │
  ├─[1] 악보 이미지 업로드 (JPG/PNG)
  │
  ├─[2] 서버 처리 (자동)
  │       OMR → 음표 추출 → 악보 생성
  │
  ├─[3] 악보 화면 표시
  │       SATB 4성부 악보 렌더링 (OSMD)
  │
  ├─[4] 재생 선택
  │       전체 합창 / S / A / T / B 클릭
  │
  └─[5] 재생 + 동기화
          음성 출력 + 악보 위치 cursor 이동
```

### 1.4 단계별 로드맵

```
1단계 (완료): 이미지 → OMR → 음표 → 모음"우" 합창 WAV
2단계 (예정): + 가사(OCR) + 음절 정렬 + 가사 가창 SVS
트랙B (예정): 교정 데이터 → OMR 모델 재학습 플라이휠
```

---

## 2. 프로젝트 구조

### 2.1 전체 디렉토리

```
aiscore/
│
├── backend/                    ← FastAPI 서버 (추론·서빙)
│   └── app/
│       ├── api/                ← HTTP 엔드포인트, 스키마
│       ├── orchestration/      ← 파이프라인 조율, 잡 상태
│       ├── stages/             ← OMR·파싱·SVS·믹싱 어댑터
│       │   ├── omr/
│       │   ├── parsing/
│       │   ├── svs/
│       │   └── mixing/
│       ├── domain/             ← 순수 Python 도메인 모델 + ports.py
│       ├── storage/            ← 파일·잡 메타 저장
│       └── core/               ← config·device·errors (횡단)
│
├── frontend/                   ← Next.js 웹 (악보 표시·재생)
│   └── src/
│       ├── app/                ← 페이지 라우팅
│       ├── components/         ← OSMD 래퍼, 오디오 플레이어
│       └── lib/                ← API 클라이언트
│
├── training/                   ← 모델 학습 (서빙 경로 밖)
│   ├── notebooks/              ← 탐색·실험용 Jupyter
│   ├── scripts/                ← 노트북 → 정리본 Python
│   ├── models/                 ← 학습 가중치 (커밋 제외)
│   └── data/                   ← 중간 산출물 (커밋 제외)
│
├── score_images/               ← 데이터 자산 (커밋 제외)
│   ├── png/                    ← 악보 이미지 645개
│   ├── xml/분리/               ← MusicXML ground truth 644개
│   ├── nwc/분리·합부/          ← NWC 원본
│   └── SOURCES.md              ← 파일 출처 기록
│
└── docs/
    ├── ROADMAP.md              ← 진행 상태 (세션 진입점)
    ├── plans/                  ← 단계별 구현 계획
    └── specs/                  ← 설계 문서 (이 파일 포함)
```

### 2.2 아키텍처 레이어 (헥사고날)

```
┌─────────────────────────────────────────────┐
│ L1  API/Gateway    backend/app/api/          │  엔드포인트, 스키마
├─────────────────────────────────────────────┤
│ L2  Orchestration  backend/app/orchestration/│  파이프라인 조율, 잡 상태
├─────────────────────────────────────────────┤
│ L3  Stages         backend/app/stages/       │  어댑터 (교체점)
├─────────────────────────────────────────────┤
│     Domain         backend/app/domain/       │  순수 모델 + ports.py
└─────────────────────────────────────────────┘
     의존성 방향: api → orchestration → stages → domain
```

**어댑터 교체점 (`OmrPort`):**

| 포트 | 현재 | 목표 |
|------|------|------|
| `OmrPort` | `ScoreUnderstandingAdapter` (YOLOv8 미학습) | `DlOmrAdapter` (학습 완료) |
| `SvsPort` | `VowelSynthAdapter` (모음"우") | `LyricSingingAdapter` (2단계) |

### 2.3 전체 데이터 흐름

```
[입력]  악보 이미지 (JPG/PNG)
    │
    ▼  backend/stages/omr/
[OMR]  이미지 → 구조화 JSON (pitch·duration·voice per 마디)
    │
    ▼  backend/stages/omr/ (후처리)
[XML]  JSON → MusicXML (결정론적 규칙 변환)
    │
    ├──▶  frontend/  →  OSMD 악보 렌더링 + cursor sync
    │
    ▼  backend/stages/svs/ + mixing/
[음성]  MusicXML → SVS 합성 → WAV 믹싱
    │
    └──▶  frontend/  →  오디오 재생
```

---

## 3. 세부 기능

---

### 3.1 Training — OMR 모델 학습

#### 개요

보유한 645쌍(이미지 800×1248px + MusicXML 644개)을 ground truth로 삼아
악보 이미지 → 구조화 JSON 변환 모델을 지도학습한다.
노트북에서 탐색·실험하고, 완성된 코드를 스크립트로 정리한 후, 학습 가중치만 백엔드에 전달한다.

#### 흐름도

```
score_images/png/           score_images/xml/분리/
hymn{NNN}_Normal.png    +   새찬송가_{NNN}*.xml
        │                           │
        │          [01_data_prep]   │
        ├───────────────────────────┤
        │                           │
        ▼                           ▼
마디 단위 크롭 이미지        마디별 JSON 라벨
(training/data/crops/)      (training/data/labels/)
        │                           │
        └──────────┬────────────────┘
                   │  [02_train_omr]
                   ▼
            모델 학습 루프
           (CNN 인코더 + Transformer 디코더)
                   │
                   ▼
          training/models/omr_v1.ckpt
                   │
                   ▼
     backend/stages/omr/dl_omr_adapter.py
           (가중치 로드 + 추론만)
```

#### 기능 구성

**`training/notebooks/01_data_prep.ipynb`**

| 단계 | 내용 |
|------|------|
| 페어링 확인 | `hymn{NNN}` ↔ `새찬송가_{NNN}` 번호 매칭, 누락 목록 |
| XML → JSON 라벨 추출 | music21로 XML 파싱 → 마디별 S/A/T/B 음표 → JSON |
| 마디 영역 검출 | OpenCV 보표선 검출 → 마디 경계 → 이미지 크롭 |
| 데이터셋 분할 | train 80% / val 10% / test 10% (곡 번호 기준) |
| 샘플 시각화 | 크롭 이미지 + 라벨 오버레이 확인 |

**`training/notebooks/02_train_omr.ipynb`**

| 단계 | 내용 |
|------|------|
| 기존 모델 검증 | Audiveris·SMT++ → 95% 미달 확인 |
| 모델 정의 | CNN 인코더(ResNet18/EfficientNet) + Transformer 디코더 |
| 학습 루프 | Cross-entropy loss, AdamW, LR 스케줄러 |
| 검증 | 음표 정확도 (pitch + duration + voice 모두 맞아야 정답) |
| 체크포인트 저장 | `training/models/omr_v{N}.ckpt` |

**`training/scripts/data_prep.py`** — 노트북 정리본, CLI 실행

```bash
python training/scripts/data_prep.py \
    --images score_images/png/ \
    --xmls score_images/xml/분리/ \
    --out training/data/
```

**`training/scripts/train_omr.py`** — 학습 실행

```bash
python training/scripts/train_omr.py \
    --data training/data/ \
    --epochs 100 \
    --out training/models/omr_v1.ckpt
```

**JSON 라벨 포맷 (모델 출력 스펙)**

```json
{
  "hymn": "001",
  "measures": [
    {
      "number": 1,
      "time_sig": "4/4",
      "key_sig": 0,
      "implicit": false,
      "parts": {
        "S": [
          {"pitch":"C5","duration":"quarter","dot":false,
           "tie_start":false,"tie_end":false,"accidental":null,"rest":false}
        ],
        "A": [...],
        "T": [...],
        "B": [...]
      }
    }
  ]
}
```

---

### 3.2 Backend — FastAPI 서버

#### 개요

이미지 업로드 → 비동기 잡 처리 → OMR·파싱·SVS·믹싱 파이프라인 실행 →
결과(MusicXML·WAV) 서빙. 헥사고날 아키텍처로 각 단계는 어댑터 교체만으로 업그레이드 가능.

#### 흐름도

```
클라이언트 (프론트엔드)
    │  POST /jobs  (이미지 업로드)
    ▼
[api/]  요청 검증 + 잡 ID 생성
    │
    ▼
[orchestration/]  파이프라인 조율 (비동기)
    │
    ├─[stages/omr/]────────────────────────────────────┐
    │   이미지 → DlOmrAdapter → JSON → MusicXML        │
    │                                                   │
    ├─[stages/parsing/]                                 │
    │   MusicXML → Music21Parser → Score 도메인 객체   │
    │                                                   │
    ├─[stages/svs/]  (4성부 병렬)                       │
    │   Score → VowelSynthAdapter → 성부별 WAV         │
    │                                                   │
    └─[stages/mixing/]                                  │
        성부별 WAV → Mixer → 합창 WAV                  │
                                                        │
잡 상태: queued→omr→parsing→synth→mixing→done/failed  ◄─┘
    │
    ▼
[storage/]  MusicXML·WAV 파일 저장, 잡 메타 관리
    │
    ▼
GET /jobs/{id}/score   → MusicXML
GET /jobs/{id}/audio   → WAV
GET /jobs/{id}/status  → 잡 상태
```

#### 기능 구성

**`api/`** — 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/jobs` | POST | 이미지 업로드 → 잡 생성 |
| `/jobs/{id}/status` | GET | 잡 상태 폴링 |
| `/jobs/{id}/score` | GET | MusicXML 파일 |
| `/jobs/{id}/audio` | GET | 전체 합창 WAV |
| `/jobs/{id}/audio/{voice}` | GET | 성부별 WAV (S/A/T/B) |
| `/jobs/{id}/meta` | GET | 조성·박자·음표 메타 |

**`orchestration/`** — 파이프라인

```
Stage1Orchestrator
  run(image_path)
    ├─ omr.run(image_path)    → xml_path
    ├─ parser.parse(xml_path) → score
    ├─ [S,A,T,B].synth(score) → wav × 4  (병렬)
    └─ mixer.mix(wavs)        → choir.wav
```

**`stages/omr/`** — OMR 어댑터

```
OmrPort (ports.py)            ← 인터페이스 (동결)
  └─ DlOmrAdapter             ← 학습 모델 (목표, 95%)
  └─ ScoreUnderstandingAdapter← YOLOv8 (현재, 미학습)
  └─ AudiverisAdapter         ← 규칙 기반 (65%, 백업)
```

**`stages/svs/`** — 성부 합성

```
SvsPort (ports.py)
  └─ VowelSynthAdapter        ← 모음"우" 합성 (현재)
  └─ LyricSingingAdapter      ← 가사 가창 (2단계)
```

**`domain/`** — 순수 도메인 (torch·fastapi import 금지)

```
Score
  └─ Part(voice: Voice)
       └─ Note(pitch, duration, tie, ...)
ports.py  ← OmrPort·SvsPort·ScoreParserPort Protocol 정의
```

---

### 3.3 Frontend — Next.js 웹

#### 개요

악보 이미지 업로드 → 잡 상태 폴링 → OSMD로 4성부 악보 렌더링 →
성부 선택 재생 + cursor 동기화. React Native(Expo) 모바일 앱도 동일 API 사용.

#### 흐름도

```
홈 페이지 (/)
    │  이미지 드래그&드롭 또는 파일 선택
    │  POST /jobs
    ▼
잡 페이지 (/jobs/{id})
    │  GET /jobs/{id}/status  (2초 폴링)
    │
    ├─[처리 중]  진행 상태 바 표시
    │             queued → omr → parsing → synth → mixing
    │
    └─[완료]
         │
         ├─ GET /jobs/{id}/score → MusicXML
         │       ↓
         │   OSMD 렌더링
         │   - SATB 4성부 악보 표시
         │   - cursor 위치 동기화
         │
         └─ GET /jobs/{id}/audio/{voice}
                 ↓
             오디오 플레이어
             - 성부 탭 (전체/S/A/T/B)
             - 재생 시 OSMD cursor 이동
```

#### 기능 구성

**`src/app/page.tsx`** — 업로드 홈

| 기능 | 설명 |
|------|------|
| 드래그&드롭 | JPG/PNG 이미지 업로드 |
| 파일 검증 | 크기·타입 클라이언트 사전 검사 |
| 잡 생성 | POST /jobs → 잡 ID 수신 → `/jobs/{id}` 이동 |

**`src/app/jobs/[id]/page.tsx`** — 결과 페이지

| 기능 | 설명 |
|------|------|
| 상태 폴링 | 2초 간격 GET /status, 완료 시 중단 |
| 진행 바 | 잡 단계별 시각화 |
| OSMD 악보 | 4성부 악보 렌더링 |
| 성부 탭 | 전체·S·A·T·B 선택 |
| 오디오 플레이어 | 재생·정지·구간 이동 |
| Cursor 동기화 | 재생 위치 → OSMD 마디/박자 하이라이트 |

**`src/components/ScoreViewer.tsx`** — OSMD 래퍼

```typescript
// MusicXML → OSMD 렌더링
// cursor API 노출: setCursorPosition(measure, beat)
// 성부 필터: showVoices(['S','A','T','B'] 중 선택)
```

**`src/components/AudioPlayer.tsx`** — 오디오 플레이어

```typescript
// 성부별 오디오 URL 관리
// 재생 이벤트 → onTimeUpdate → ScoreViewer.setCursorPosition()
```

---

### 3.4 데이터 자산 관리

#### 파일 출처

`score_images/SOURCES.md` 에 모든 데이터 출처 기록.

#### 커밋 정책 (`.gitignore`)

| 제외 대상 | 이유 |
|----------|------|
| `score_images/**/*.png/jpg/nwc/xml` | 대용량 바이너리 |
| `training/models/*.ckpt` | 대용량 모델 가중치 |
| `training/data/` | 중간 산출물 |
| `backend/data/` | 런타임 산출물 |

#### 이미지-XML 페어링 규칙

```
score_images/png/hymn001_Normal.png
    ↕ (번호 매칭)
score_images/xml/분리/새찬송가_001 만복의근원하나님.xml
```

유효 쌍: 644개 (133·315번 등 3개 변환 실패 제외)

---

## 4. 개발 절차 요약

```
[탐색]  training/notebooks/*.ipynb
    ↓  코드 동작 확인 후
[정리]  training/scripts/*.py
    ↓  가중치 산출
[배포]  backend/stages/omr/dl_omr_adapter.py
    ↓  OmrPort 어댑터 교체
[검증]  E2E 테스트 (이미지 → OSMD 렌더링 확인)
```

**코드 경계 규칙:**

| 위치 | 허용 | 금지 |
|------|------|------|
| `training/` | 학습·실험·전처리 전부 | 서빙 경로 코드 |
| `backend/stages/omr/` | 모델 로드·추론·OmrPort 구현 | 학습 루프·데이터 전처리 |
| `domain/` | 순수 Python | torch·fastapi import |

---

## 5. 학습 모델

### 5.1 모델 아키텍처: OmrCRNN

OMR 인식에는 **CRNN (Convolutional Recurrent Neural Network)** 구조를 채택한다. 악보 이미지를 왼쪽→오른쪽으로 슬라이딩하며 음표 시퀀스를 출력하는 구조로, OCR·악보 인식 분야에서 검증된 기준선 방법론이다.

```
입력 이미지 (B, 3, 128, 2048)
       ↓
ResNet18 백본 (ImageNet 사전학습)
  maxpool → Identity (stride 32→16)
  마지막 FC + avgpool 제거
       ↓
feature map (B, 512, 8, 128)
       ↓
AdaptiveAvgPool2d — 세로 압축 (B, 512, 1, 128)
       ↓
BiLSTM 2층 (hidden=256×2=512) → (B, 128, 512)
       ↓
S / A / T / B 독립 Linear 헤드
       ↓
CTC Loss (alignment-free 시퀀스 학습)
```

### 5.2 백본: ResNet18

| 항목 | 내용 |
|------|------|
| **출처** | torchvision 공식 제공 (`torchvision.models.ResNet18_Weights.DEFAULT`) |
| **원본 논문** | *Deep Residual Learning for Image Recognition* (He et al., 2015, Microsoft Research) |
| **사전학습 데이터** | ImageNet — 1,000 카테고리, 약 120만 장 자연 이미지 |
| **파라미터 수** | 약 11M |
| **역할** | 악보 이미지의 국소 특징(선, 음표 헤드, 보표 등) 추출 |

**선택 이유:**

| 기준 | 이유 |
|------|------|
| 데이터 부족 | 630쌍으로 처음부터 학습 불가 → ImageNet 사전학습 필수 |
| Transfer Learning | 자연 이미지 특징(엣지·곡선·텍스처)이 악보 인식에도 유효 |
| 경량 | ResNet50/101 대비 파라미터 적어 소규모 데이터 과적합 위험 ↓ |
| CRNN 표준 | OMR·OCR 분야 검증된 CNN 백본 + BiLSTM + CTC 조합 |

### 5.3 수정 사항

원본 ResNet18에서 두 가지를 변경했다.

```python
backbone.maxpool = nn.Identity()  # stride 32→16 으로 완화
encoder = nn.Sequential(*list(backbone.children())[:-2])  # FC + avgpool 제거
```

- **maxpool 제거:** stride를 32→16으로 줄여 시간축(T) 프레임을 8→128로 확보. CTC는 T ≥ target_length 조건이 필요하므로 이 수정이 핵심이다.
- **FC + avgpool 제거:** 분류가 아닌 sequence-to-sequence 출력이 필요하므로 공간 feature map을 유지한다.

### 5.4 Vocabulary (NoteVocab)

| 범주 | 내용 | 수 |
|------|------|----|
| 특수 토큰 | `<BLK>` (CTC blank), `<EOS>`, `TIE_S`, `TIE_E` | 4 |
| 음정 | C·D·E·F·G·A·B × 옥타브 2~6 × 제자리·♭·♯ + REST | 106 |
| 음가 | 16분·8분·점8분·4분·점4분·2분·점2분·점4분·온음표 (9종) | 9 |
| **합계** | | **119** |

인코딩: 음표 1개 → `pitch 토큰` + `DUR 토큰` (+ 필요시 `TIE_S/TIE_E`). CTC target에 EOS 미포함(blank만 사용).

### 5.5 학습 설정

| 항목 | 값 |
|------|-----|
| 입력 크기 | 128 × 2048 (H × W), grayscale→RGB 변환 |
| 배치 크기 | 8 |
| 에포크 | 30 |
| 옵티마이저 | Adam (lr=1e-4) |
| 손실 함수 | CTCLoss (blank=0, zero_infinity=True) |
| 학습/검증/테스트 분할 | 80 / 10 / 10 % (630쌍 기준) |
| 디바이스 | MPS (Apple Silicon) — CTC는 CPU fallback (`PYTORCH_ENABLE_MPS_FALLBACK=1`) |
| 체크포인트 | `training/models/omr_crnn_best.pt` (val_loss 최소 기준) |

### 5.6 파일 위치

| 파일 | 역할 |
|------|------|
| `training/scripts/train_omr.py` | OmrCRNN 모델 정의 + 학습 루프 |
| `training/scripts/data_prep.py` | MusicXML → JSON 라벨 추출 |
| `training/notebooks/02_train_omr.ipynb` | 학습 실행 노트북 |
| `training/models/omr_crnn_best.pt` | 최적 체크포인트 (git 미추적) |
| `backend/app/stages/omr/dl_omr_adapter.py` | 추론 어댑터 (OmrPort 구현) |
