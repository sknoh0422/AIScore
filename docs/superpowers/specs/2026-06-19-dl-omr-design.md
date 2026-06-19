# DL 기반 OMR 재설계 — 설계 문서

> **작성일:** 2026-06-19  
> **배경:** Audiveris OMR 심층 진단 결과, 찬송가 315장 소프라노 검출 정확도 65% (52음 중 34음 검출, 4개 마디 전체 누락). 규칙 기반 OMR의 한계 확인 → 딥러닝 기반 재개발 결정.  
> **연계:** [ROADMAP.md](../../ROADMAP.md) | [ARCHITECTURE.md](../../ARCHITECTURE.md) | [CLAUDE.md](../../../CLAUDE.md)

---

## 1. 문제 정의

### 1.1 현재 파이프라인의 한계

```
악보 이미지 → Audiveris(규칙 기반 OMR) → MusicXML → 파싱
               ↑
               여기가 병목: 65% 정확도
```

**관찰된 오류 유형:**

| 오류 유형 | 예시 | 비율 |
|----------|------|------|
| 마디 전체 누락 | m1,m6,m11,m16 음표 전무 | 심각 |
| 피치 오인식 | D5→정답A, G5→정답Bb | 빈번 |
| Voice 구조 혼재 | Voice1/flat 불규칙 | 파싱 난이도 ↑ |
| 이음줄(tie) 미처리 | 이어진 음표 재공격 | 중간 |

### 1.2 목표

1. **찬송가 특화 OMR**: 한국 찬송가(4성부 SATB, 4/4박자 위주)에 최적화
2. **로컬 추론**: 외부 API 없이 온디바이스 실행(§16 규칙 준수)
3. **점진적 정확도 향상**: 교정 데이터 누적 → 재학습(플라이휠)
4. **헥사고날 호환**: `OmrPort` 어댑터 교체만으로 통합

---

## 2. OMR 태스크 분해

악보 이미지 → MusicXML 변환은 다음 서브태스크로 구성됩니다:

```
Stage 1: 이미지 전처리
  └─ 이진화(binarization) · 노이즈 제거 · DPI 정규화

Stage 2: 레이아웃 분석 (Layout Analysis)
  ├─ 보표 선(staff line) 검출
  ├─ 시스템(system) 경계 검출
  └─ 마디선(barline) 검출 → 마디 영역 분리

Stage 3: 기호 인식 (Symbol Recognition)
  ├─ 음표머리(notehead) 검출 + 선/간 위치 → 음이름(피치)
  ├─ 음표 형태 분류 → 음가(duration: 온음/2분/4분/8분...)
  ├─ 올림표/내림표/제자리표(accidental) 검출
  ├─ 줄기(stem) · 보(beam) · 깃발(flag) 분석 → 음가 보정
  ├─ 이음줄(slur) · 붙임줄(tie) 검출
  └─ 쉼표(rest) 검출 + 분류

Stage 4: 성부 분리 (Voice Assignment)
  ├─ 줄기 방향(up/down) → 소프라노/알토 분리 (트레블보표)
  └─ 줄기 방향(up/down) → 테너/베이스 분리 (베이스보표)

Stage 5: 구조화 (Structuring)
  └─ 음표 + 타이밍 → MusicXML 생성
```

---

## 3. 접근 방법 비교

### 옵션 A: 기존 DL-OMR 모델 파인튜닝

| 항목 | 내용 |
|------|------|
| 대상 모델 | **SMT / SMT++** (트랜스포머 기반 폴리포닉 OMR, 2023~2024) |
| 방식 | 공개 가중치 + 찬송가 데이터로 파인튜닝 |
| 장점 | 기존 검증된 아키텍처 활용, 빠른 시작 |
| 단점 | 찬송가 한국어 가사 미지원, 아키텍처 제약 |
| 난이도 | 중 |

### 옵션 B: 오브젝트 디텍션 파이프라인 (권장 - 1차)

| 항목 | 내용 |
|------|------|
| 기반 모델 | **YOLOv8** (notehead/accidental/rest 검출) + 보표 선 추적 |
| 방식 | 음악 기호 OD → 규칙 기반 MusicXML 조립 |
| 장점 | 모듈별 디버깅 용이, 데이터 생성 간단 (MusicXML → 렌더→레이블) |
| 단점 | 복잡한 post-processing, 오류 전파 |
| 난이도 | 중 |

### 옵션 C: 이미지-시퀀스 트랜스포머 (권장 - 2차)

| 항목 | 내용 |
|------|------|
| 기반 모델 | **TrOMR** / **MUSCIMA E2E** / 자체 ViT+디코더 |
| 방식 | 보표 이미지 → 악보 토큰 시퀀스(Kern/MEI) → MusicXML |
| 장점 | End-to-End, 복잡한 규칙 제거 |
| 단점 | 대용량 데이터 필요, 학습 난이도 높음 |
| 난이도 | 상 |

### 옵션 D: VLM 활용 (보조)

| 항목 | 내용 |
|------|------|
| 모델 | LLaVA / 로컬 멀티모달 LLM |
| 방식 | 보표 이미지 → 음표 이름 열거 프롬프팅 |
| 장점 | 즉시 시험 가능, 제로샷 |
| 단점 | 정확도 미성숙, 할루시네이션, 로컬 실행 무거움 |
| 난이도 | 하 (사용) / 상 (정확도) |

### 단계적 추진 전략

```
1차 (단기): 옵션 B — YOLOv8 오브젝트 디텍션
  → 음표머리 검출 정확도 측정 → 빠른 피드백
  → 데이터: 렌더링 기반 합성 데이터 (MusicXML→PNG 자동 생성)

2차 (중기): 옵션 A — SMT++ 파인튜닝
  → 찬송가 데이터 충분히 쌓인 후
  → SATB 폴리포닉 처리 강점 활용

3차 (장기): 옵션 C — 자체 E2E 트랜스포머
  → 교정 데이터 플라이휠이 충분히 돌아간 후
```

---

## 4. 학습 데이터 전략

### 4.1 데이터 소스

| 소스 | 종류 | 규모 | 획득 방법 |
|------|------|------|---------|
| **합성 데이터** (1순위) | MusicXML→이미지 렌더링 | 무제한 생성 가능 | MuseScore/Lilypond 렌더링 |
| **CPDL** (Choral Public Domain Library) | 합창 MusicXML | ~3,000곡 | 공개 다운로드 |
| **MuseScore 커뮤니티** | 찬송가 MusicXML | 수천 곡 | 크롤링(이용약관 확인) |
| **Hymnary.org** | 찬송가 악보 PDF/이미지 | ~45,000 곡 | PDF 분할 |
| **한국찬송가** | 직접 스캔 | 645장 | 수동 스캔 + 교정 |
| **교정 누적 (L4)** | 사용자 교정 라벨 | 점진적 증가 | AIScore 플라이휠 |

### 4.2 합성 데이터 생성 파이프라인 (핵심)

```
MusicXML (CPDL/MuseScore)
  ↓ Lilypond/MuseScore 렌더링
이미지 (다양한 해상도/폰트/인쇄품질 시뮬레이션)
  ↓ 자동 레이블 생성 (MusicXML에서 직접 추출)
(이미지, 음표 바운딩박스, 피치, 음가) 학습 쌍
```

**증강(augmentation) 전략:**
- 해상도 변화 (150~400 DPI)
- 가우시안 노이즈, 모션 블러 (스캔 품질 시뮬레이션)
- 기울기(skew) ±5°
- 밝기/대비 조정
- 인쇄체 → 손글씨 스타일 변환 (선택)

### 4.3 어노테이션 포맷

```json
{
  "image": "hymn315_m1.png",
  "staves": [
    {
      "type": "treble",
      "y_top": 120, "y_bottom": 180,
      "notes": [
        {"x": 45, "y": 140, "pitch": "F4", "duration": "quarter", "voice": 1, "tie": false},
        {"x": 90, "y": 130, "pitch": "A4", "duration": "quarter", "voice": 1, "tie": false}
      ]
    }
  ]
}
```

---

## 5. 아키텍처 설계 (1차: YOLOv8 파이프라인)

### 5.1 모듈 구성

```
training/
├── data/
│   ├── raw/              # 원본 MusicXML, PDF
│   ├── rendered/         # 렌더링된 이미지
│   └── annotations/      # YOLO 포맷 레이블
├── scripts/
│   ├── render_scores.py  # MusicXML → PNG (Lilypond/MuseScore)
│   ├── generate_labels.py# MusicXML → YOLO 바운딩박스 레이블
│   └── augment.py        # 증강 파이프라인
├── models/
│   ├── staff_detector/   # 보표선 검출 (Hough / CNN)
│   ├── symbol_detector/  # YOLOv8 음악 기호 검출
│   └── pitch_classifier/ # 보표 상 위치 → 피치 분류
└── eval/
    ├── metrics.py         # 음표 단위 정밀도/재현율, 마디 정확도
    └── compare.py         # 정답 MusicXML vs 검출 결과 비교
```

### 5.2 서빙 어댑터

```python
# backend/app/stages/omr/dl_omr_adapter.py
class DlOmrAdapter:
    """OmrPort 구현 — YOLOv8 기반 DL-OMR."""

    def __init__(self, model_path: Path, work_dir: Path):
        self._model = YOLO(model_path)
        self._work_dir = work_dir

    def run(self, image_path: Path) -> Path:
        # 1. 보표선 검출 → 마디 분리
        # 2. YOLOv8 음표머리/기호 검출
        # 3. 보표 위치 → 피치 변환
        # 4. 줄기 방향 → 성부 분리
        # 5. MusicXML 조립
        ...
```

헥사고날 아키텍처의 `OmrPort`를 구현하므로, 오케스트레이터는 변경 없이 그대로 사용.

---

## 6. 평가 지표

### 음표 단위 (Note-level)

| 지표 | 정의 | 목표 |
|------|------|------|
| 음표 검출률(Recall) | 정답 음표 중 검출된 비율 | ≥ 90% |
| 음표 정밀도(Precision) | 검출 음표 중 정답 비율 | ≥ 90% |
| 피치 정확도 | 검출된 음표 중 피치 맞은 비율 | ≥ 95% |
| 음가 정확도 | 검출된 음표 중 음가 맞은 비율 | ≥ 90% |

### 현재 Audiveris 기준선 (315장)

| 지표 | Audiveris | 목표 |
|------|-----------|------|
| 소프라노 검출률 | 65% (34/52) | ≥ 90% |
| 마디 전체 누락 | 4/20마디 | 0 |
| 피치 정확도 | ~70% (추정) | ≥ 95% |

---

## 7. 개발 로드맵

### Phase 0: 데이터 파이프라인 구축 (2~3주)
- [ ] CPDL/MuseScore에서 찬송가 MusicXML 수집 (목표: 500곡 이상)
- [ ] Lilypond 렌더링 스크립트 (`training/scripts/render_scores.py`)
- [ ] YOLO 포맷 자동 레이블 생성 (`training/scripts/generate_labels.py`)
- [ ] 증강 파이프라인 구축

### Phase 1: 보표/마디선 검출 (1~2주)
- [ ] 보표선 검출기 구현 (Hough transform 또는 경량 CNN)
- [ ] 마디선 검출기
- [ ] 마디 영역 자르기 → 개별 이미지 분리

### Phase 2: 음표 검출 모델 (3~4주)
- [ ] YOLOv8n 파인튜닝 (notehead, rest, accidental 클래스)
- [ ] 찬송가 합성 데이터 1,000장으로 초기 학습
- [ ] 검출률 측정 — 315장 기준선 대비 비교

### Phase 3: 피치/음가 분류 + 성부 분리 (2~3주)
- [ ] 보표 위치(라인/스페이스) → 피치 변환 로직
- [ ] 음표 형태 분류기 (4분음표/2분음표/온음표/점음표 등)
- [ ] 줄기 방향 → 성부(Voice1/Voice2) 분리

### Phase 4: MusicXML 조립 + 통합 (2주)
- [ ] MusicXML 생성기
- [ ] `DlOmrAdapter` (`OmrPort` 구현)
- [ ] 기존 파이프라인 통합 — 오케스트레이터 변경 없이 어댑터 교체
- [ ] E2E 테스트: 315장 → choir.wav 검증

### Phase 5: 교정 플라이휠 (지속)
- [ ] L4 교정 레코더 → DL 학습 데이터 누적
- [ ] 주기적 재학습 스크립트 (`training/retrain.py`)

---

## 8. 기술 선택 근거

### YOLOv8 선택 이유
- PyTorch 기반 (기존 `torch/MPS` 환경 그대로 사용)
- 사전 학습 가중치 공개, 파인튜닝 용이
- 음악 기호 검출에 충분한 선례 (DeepScores 데이터셋 등)
- Apple Silicon MPS 지원

### Lilypond 렌더링 선택 이유
- MusicXML → Lilypond 변환 라이브러리 존재 (music21)
- 고품질 벡터 → 래스터화, 다양한 폰트/스타일 지원
- 완전 오픈소스, 로컬 실행

### 데이터 전략 핵심: 합성 데이터 우선
- 찬송가 악보 스캔 어노테이션은 인력 집약적
- MusicXML → 이미지 자동 생성으로 초기 수천 샘플 확보 가능
- 실제 스캔 이미지는 파인튜닝/검증용으로 활용

---

## 9. 의존성 추가 예정

```yaml
# aiscore_env.yml 추가 예정
dependencies:
  - ultralytics     # YOLOv8 (pip)
  - lilypond        # 악보 렌더링 (brew/apt)
  - music21         # 기존 (MusicXML 조작)
```

---

## 10. 참고 문헌

- **SMT/SMT++**: "End-to-End Full-Page Optical Music Recognition for Pianoforms" (2023)
- **DeepScores v2**: 악보 기호 오브젝트 디텍션 데이터셋 (21개 클래스)
- **MUSCIMA++**: 수기 악보 어노테이션 데이터셋
- **oemer 소스**: 단성부 OMR의 전처리/보표선 검출 참고
- **Audiveris 소스**: 규칙 기반 OMR의 마디선/성부 처리 참고
