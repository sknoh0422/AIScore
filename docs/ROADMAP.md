# AIScore 로드맵 / 진행 상태

> **새 세션 진입점.** 이 프로젝트를 이어서 작업할 때 이 파일 하나만 열면 현재 상태와 다음 작업을 알 수 있다.
> 규약은 [CLAUDE.md](../CLAUDE.md), 설계 원칙은 [Why 문서](specs/design-why.md), 소스 구조·흐름은 [How 문서](specs/aiscore-system-design.md).

**최종 갱신:** 2026-06-23 (8차)

---

## 새 세션 시작 방법
1. `CLAUDE.md`는 자동 로드된다(프로젝트 규약).
2. 이 `docs/ROADMAP.md`를 읽어 현재 상태/다음 작업을 파악한다.
3. 진행 중 단계의 계획서(아래 링크)를 열어 미체크 태스크부터 이어간다.
4. 환경: `conda activate`가 비대화형 셸에서 실패하면 `/opt/miniconda3/envs/aiscore/bin/python` 절대경로 사용.

---

## ✅ 완료
- **프로젝트 설계 확정** — (헥사고날, 1/2단계 로드맵, 트랙B)
- **CLAUDE.md** — 이중 오케스트레이션·레이어·라우팅·병렬화·절대규칙 20
- **스캐폴딩** — backend/frontend/training 구조, 동결된 `backend/app/domain/ports.py`
- **1단계 파이프라인 (image→OMR→SATB→모음"우"→믹싱)** — main 통합 완료, 단위 테스트 16 passed
  - 계획: (1단계 계획 — 완료)
  - 구현: OMR(oemer)·파싱(music21)·SVS(VowelSynth)·믹싱 어댑터 + 오케스트레이터(4성부 병렬) + FastAPI 잡 API
- **Audiveris OMR 스테이지 (image→Audiveris→N성부)** — main 통합 완료, 단위 24 passed + E2E(315.JPG→choir.wav 18s) 검증
  - 계획: (Audiveris 계획 — 완료)
  - 구현: 전처리(업스케일) + `audiveris_adapter`(JDK25 배치) + `part×voice` 무손실 파서 + 존재 성부만 합성 + 업로드 검증. 실제 SATB는 트레블/베이스 2성부 가이드(완전 4성부는 교정 영역).
- **품질 개선 5종** — 33 passed, main 통합 완료 (`716cad9`)
  - ParseError 추가 + 파서 0-파트 방어 / 업로드 OOM 방어(`read(_MAX_BYTES+1)`) / 믹서 스테레오→모노 변환+samplerate 수정 / Store 격리(root 파라미터+reset, conftest autouse) / test_ports.py 포트 계약 테스트 5종 / pyproject.toml integration 마크 기본 제외
- **프론트엔드 (Next.js + OSMD)** — main 통합 완료 (`924a282`)
  - Next.js 15 + Tailwind v4 + TypeScript 5. 업로드 홈(드래그&드롭) → 잡 페이지(2초 폴링+진행 바+오디오 플레이어+OSMD 악보 렌더)
  - 백엔드 추가: CORS, score_path 추적, `/audio` · `/score` FileResponse 엔드포인트
  - 실행: `uvicorn app.main:app --reload` (포트 8000) + `npm run dev` (포트 3000)
- **Score Understanding Pipeline (DL-OMR 5모듈)** — main 머지 완료 (`e50e493`, 2026-06-22), 88 passed
  - 계획·설계: (완료, 파일 통폐합됨)
  - 구현: 전처리 → 레이아웃 분석 → YOLOv8 OMR 엔진 → 메타 추출 → 가사 OCR(PaddleOCR) → MusicXML 조립 → `ScoreUnderstandingAdapter(OmrPort)`
  - 현재 상태: YOLOv8 모델 미학습(더미 패스스루). 다음 단계 = 모델 학습(Plan 1B)
- **MD 파일 체계 재구성** — `docs/superpowers/` 제거, `docs/plans/` · `docs/specs/` · `raw/project_start.md` 정착
- **Plan 1B — OMR 모델 학습 파이프라인 구축** — `feat/plan-1b-omr-training` 브랜치, main 머지 대기 중 (2026-06-23)
  - 계획서: [`docs/plans/2026-06-23-plan-1b-omr-training.md`](plans/2026-06-23-plan-1b-omr-training.md)
  - `training/scripts/data_prep.py` — XML→JSON 라벨 630쌍 추출, train480/val60/test60 분할
  - `training/scripts/baseline_eval.py` — Audiveris 기준선 평가 (≈65%, 자체 학습 정당화)
  - `training/scripts/train_omr.py` — CRNN(ResNet18+BiLSTM+CTC), vocab 119토큰, T=128, MPS 지원
  - `training/notebooks/01_data_prep.ipynb`, `02_train_omr.ipynb` — 실험 래퍼
  - `backend/app/stages/omr/dl_omr_adapter.py` — `DlOmrAdapter(OmrPort)` 구현
  - `backend/app/core/config.py` — `dl_omr_model_path()` 추가
  - E2E 확인: `hymn001_Normal.png` → 추론 → MusicXML 2389 bytes 생성
  - **현재 상태:** 2 epoch 스모크 학습 완료(val_loss 6.59→6.12). **30 epoch 전체 학습 미완료** → 정확도 미검증

## ⏳ 대기 / 검증 필요
- **고해상도 악보 OMR 검증** — 315.JPG 저해상도(500×777px)로 소프라노 검출 34/52음(65%), 4개 마디 전체 누락. 300 DPI 스캔본으로 재검증 필요.
- **Plan 1B 브랜치 머지** — `feat/plan-1b-omr-training` → main 머지 승인 대기

## 📋 예정 (우선순위순)

### 🔴 최우선: Plan 1B 후속 — CRNN 전체 학습 + 정확도 달성

> **현재 상태:** 파이프라인 구축 완료, 2 epoch 스모크 학습만 진행됨. 30 epoch 전체 학습 필요.

**다음 작업:**
1. `feat/plan-1b-omr-training` → `main` 머지
2. `PYTORCH_ENABLE_MPS_FALLBACK=1 /opt/miniconda3/envs/aiscore/bin/python training/scripts/train_omr.py` — 30 epoch 전체 학습 실행 (수 시간 소요)
3. val set 음표 정확도 측정 — 95% 미달 시 데이터 증강(회전·밝기·노이즈) 추가 후 재학습
4. 다페이지 이미지(2400px+, 16개) 처리 개선 — 현재 Resize 압축 → 페이지 분할 전처리 고려
5. `DlOmrAdapter`를 오케스트레이터에 기본 어댑터로 연결

---

- **L4 교정 로깅** — 교정 결과를 (이미지영역, 오답, 정답) 라벨로 누적(DL 학습 데이터 플라이휠).
- **모바일 앱 (React Native + Expo)** — 계획서 완료. [계획서](plans/plan-mobile-app.md)
- **2단계 가사** — 텍스트 입력/OCR + 음절↔음표 정렬 + 가사 가창 SVS.

---

## 진행 이력 (날짜별)

### 2026-06-16
- 프로젝트 **브레인스토밍 → 설계 확정**: 제품 정의, 1/2단계 로드맵, 트랙B(오프라인 OCR 학습), 기술 타당성(가사는 OMR 분리, 모음"우" 우회) 결정.
- **설계 문서** 작성: `docs/superpowers/specs/2026-06-16-aiscore-design.md`.
- **CLAUDE.md**(헌법) 작성 + **빈 스캐폴딩** 생성(backend/frontend/training, 동결된 `ports.py`) — 커밋 `27733e8`.
- **1단계 구현 계획**(TDD 9태스크) 작성 — 커밋 `012612c`.
- GitHub 레포 연결: `sknoh0422/AIScore`.

### 2026-06-16 ~ 06-17
- **1단계 파이프라인 구현**(서브에이전트 주도 TDD, 8태스크): `to_midi`/하니스 → VowelSynth("우") → Mixer → Music21Parser → OemerAdapter → Job → Stage1Orchestrator(4성부 병렬) → FastAPI 잡 API.
- **최종 코드 리뷰** → 크리티컬 2건 수정: ① `to_midi` music21 플랫 표기(`B-4`) 처리 ② 잡 상태 실행 중 가시화(on_update 콜백).
- `feat/stage1-vowel-choir` → **`main` squash 머지** — 커밋 `1722cb6`, 단위 테스트 **16 passed**(통합 1 deselected).
- **ROADMAP.md** 추가(단일 진입점) + 날짜별 이력 정리.

### 2026-06-17 (OMR 실측 검증)
- 샘플 OMR 검증: `온맘다해.png`(단성부) → oemer **정상**. `315.JPG`(밀집형 SATB) → oemer **크래시**(`build_system.align_symbols: assert track_nums == 2`, 검출 3), MusicXML 미생성.
- 결론: oemer는 2-track 가정이라 밀집형 SATB 부적합 → **Audiveris 어댑터로 전환 필요**(설계가 자리만 잡아둔 교체점). 파이프라인은 OMR 실패를 `failed`로 정상 표면화 확인.

### 2026-06-17 (OMR 후보 조사 → Audiveris 결정)
- 후보 비교(통합 가능성·로컬/프라이버시·SATB·MusicXML 기준):
  - **Audiveris**(OSS/Java, CLI 서버통합, 로컬, MusicXML, 교정 가능) → **채택**. 단 T/B 베이스보표 공유 시 "3성부+피아노" 오인식 한계 있음(교정 에디터로 보완).
  - oemer = 단성부 전용으로 강등. **SMT/SMT++**(트랜스포머, 폴리포닉) = 장기 고천장 백로그.
  - 상용(PlayScore/SmartScore/PhotoScore 등) = **공개 API 없음 + 사용자 악보 외부 전송(규칙 D16 위배)** → 자동 백엔드 부적합. VLM(Gemini/GPT-4o) = 정확도 미성숙 + 외부전송 → 비권장.
- 핵심 통찰: SATB 다성부 분리는 OMR 본질적 난제(상용도 약함) → **교정 에디터 필수**. 파서를 Part 단위가 아니라 **staff×voice** 기준으로 보강 필요.
- 다음: Audiveris 설치 가능성(Java/JVM) 확인 → 315.JPG 실측 → `audiveris_adapter` spec→plan→TDD.

### 2026-06-17 (Audiveris 빌드·실측 — 핵심 발견)
- JDK 25(`brew openjdk@25`) + **Audiveris 5.10.2 소스 빌드 성공**. (JDK 26은 Gradle 9.1 미지원 `class major 70` → 25 사용)
- 315.JPG **원본(500×777)** → Audiveris도 PAGE 실패. **근본 원인 = 저해상도**(interline 6px, "too low ... try 300 DPI"). **oemer 크래시도 동일 원인**.
- **3× 업스케일(LANCZOS) → Audiveris 성공**: score-part **2**(트레블 S/A + 베이스 T/B), clef **G+F**, 8 보표, 12 마디, 가사~0. SlursBuilder NPE 경고 있으나 비치명적(.mxl 정상 export).
- 결론: ① **OMR 전처리(업스케일/DPI 정규화)가 필수 단계** ② SATB는 **2-part grand-staff(클레프별)** 인코딩 → 파서를 `part×voice → S/A/T/B` 매핑으로 보강 ③ **Audiveris 어댑터 진행 타당**(설치/빌드/배치 검증 완료).
- 빌드 산출물(로컬, 미커밋): `/tmp/audiveris/app/build/distributions/app-5.10.2` (배치: `bin/Audiveris -batch -transcribe -export -output <dir> <img>`, JDK25 JAVA_HOME 필요).

### 2026-06-17 (Audiveris OMR 구현 완료)
- 환경: `openjdk@25` 설치(JDK26은 Gradle 9.1 미지원), Audiveris 5.10.2 소스 빌드 → `vendor/audiveris/`(gitignore).
- 서브에이전트 주도 TDD 7태스크: config → 전처리(업스케일) → `audiveris_adapter` → `part×voice` 파서 → N성부 오케스트레이터 → 배선.
- 최종 리뷰 → 수정: `.mxl` 결정적 경로(pre.mxl)+잡별 디렉터리, **업로드 검증(content-type/크기/실이미지, §14)**, 파서 무손실(파트당 전체 음표), config int 가드.
- 검증: 단위 **24 passed**, **E2E** `315.JPG`(업스케일) → Audiveris → 합창 WAV 18s. `feat/audiveris-omr` → `main` squash 머지 `0eacf9b`.
- 한계: 실제 SATB는 OMR이 트레블/베이스 **2성부**로 인식(완전 4성부 분리는 교정 에디터/후속). 런타임은 `vendor/` Audiveris 빌드본 + JDK25 필요(이식 시 재빌드).

### 2026-06-18 (품질 개선 + 프론트엔드)
- **품질 개선 5종** — `feat/quality-improvements` → main (`716cad9`). 33 tests passed.
  - ParseError / 업로드 OOM 방어 / 믹서 스테레오→모노+samplerate / Store 격리+conftest / test_ports.py 계약 테스트 / integration 마크 기본 제외.
- **프론트엔드 초기 구현** — `feat/frontend` → main (`924a282`).
  - Next.js 15 + Tailwind v4 + TypeScript 5 + OSMD.
  - 업로드 홈(드래그&드롭) → `/jobs/{id}` 페이지(2초 폴링, 진행 바, 오디오 플레이어, OSMD 악보 렌더).
  - 백엔드: CORS, score_path, `/audio`·`/score` FileResponse 추가.
- `docs/ARCHITECTURE.md` 구조 설명서 작성.

### 2026-06-18 (성악품질개선 + OMR검증 + 모바일설계 + feat/vocal-quality 머지)
- **4성부 화음 분리** (`music21_parser.py`) — `_split_two_voices()`로 Part별 chord 상단/하단 분리. 악기 파트(Piano/Organ 등) 필터링, 성악 파트만 추출. 3+ 피치 코드 중간음 제거 경고 로그 추가.
- **성악 합성 품질 개선** (`vowel_synth_adapter.py`) — 포먼트 IIR 필터 + 성부별 비브라토(Fleming/Ferrier/Pavarotti/Ramey 모델). timing.json BPM과 오디오 BPM 동기화.
- **timing.json** — `core/timing.py`(횡단 유틸)로 이동(레이어 위반 해소). 성부별 음표 시작/종료 시각 JSON + `GET /timing` 엔드포인트.
- **성부별 WAV 엔드포인트** — `GET /jobs/{id}/audio/{voice}` 추가.
- **악보 메타 API** — `core/score_meta.py` 신설. `GET /jobs/{id}/meta` → 조성·박자·성부·소프라노 음표 JSON. `GET /jobs/{id}/image` → 원본 이미지 서빙.
- **웹 UI 개선** — 성부별 오디오 플레이어(S/A/T/B), 원본 악보 이미지 + 소프라노 음표 나란히 표시(4마디/줄, 세로선 구분, 불완전 마디 레이블).
- **OMR 정확도 실측** — 315.JPG(500×777px): 소프라노 34/52음 검출(65%). 4개 마디(m1,m6,m11,m16) 전체 누락. 저해상도 한계.
- **모바일 앱 설계 확정** — React Native+Expo. 계획서 `2026-06-18-mobile-app.md` 완료.
- `feat/vocal-quality` → main squash 머지 완료.

### 2026-06-23 (Plan 1B — OMR 학습 파이프라인 구축)
- **Plan 1B 6태스크 완료** — `feat/plan-1b-omr-training` 브랜치, 서브에이전트 주도 TDD
  - **데이터 준비**: `data_prep.py` — XML 630쌍 JSON 라벨 변환(Chord 처리 포함), train/val/test 분할
  - **기준선 평가**: `baseline_eval.py` — Audiveris ≈65% 확인(자체 학습 정당화)
  - **CRNN 모델**: `train_omr.py` — ResNet18(`maxpool=Identity`, stride 16) + BiLSTM + 4성부 CTC, vocab 119토큰, `IMG_W=2048,IMG_H=128`(T=128)
  - **노트북**: `01_data_prep.ipynb`, `02_train_omr.ipynb`
  - **백엔드 어댑터**: `dl_omr_adapter.py` — `DlOmrAdapter(OmrPort)`, `torch.load weights_only=False` (vocab dict 포함)
  - **config**: `dl_omr_model_path()` — `DL_OMR_MODEL_PATH` 환경변수 지원
  - E2E 스모크: `hymn001_Normal.png` → MusicXML 2389 bytes 생성 확인
  - 2 epoch 학습: val_loss 6.59→6.12. 30 epoch 전체 학습은 별도 실행 필요
- **브랜치**: `feat/plan-1b-omr-training` — main 머지 승인 대기

### 2026-06-23 (NWC 전곡 확보 + OMR 학습 방향 확정)
- **NWC 전곡 확보** — risen.runean.com(CDN) + Daum 카페 백업 소스로 003~009·490 분리악보 보완
  - 분리악보: 645개 (100% 확보), 합부악보: 553개 (490 합부 CDN 404 → 스킵)
  - MusicXML 변환 완료: 644개. 실패 3개(133·315·?) — music21 미지원 오브젝트
  - 출처 기록: `score_images/SOURCES.md`
- **OMR 학습 전략 확정** (토론 기반)
  - Ground truth: 분리악보 XML 644개 (NWC→music21→MusicXML 변환본)
  - 모델 입력: 악보 이미지 (800×1248, 10~15마디/페이지)
  - 모델 출력: **구조화 JSON** (마디별 음표 이벤트 — pitch/duration/voice/accidental/tie)
  - 서버 후처리: JSON → MusicXML (결정론적 규칙)
  - 프론트엔드: MusicXML → OSMD (악보 표시·cursor sync) + SVS/MIDI (성부 재생)
  - 개발 흐름: `training/notebooks/` → `training/scripts/` → `backend/stages/omr/` (추론만)
- **설계 문서 신규 작성** — [OMR 학습 파이프라인 설계](specs/aiscore-system-design.md)

### 2026-06-22 (Score Understanding Pipeline 머지 + MD 체계 정리)
- **Score Understanding Pipeline** (`feat/score-understanding-pipeline`) → main 머지 완료.
  - 12커밋, 25파일, 1299줄 추가. 88 tests passed.
  - 5모듈: 전처리 → 레이아웃 → YOLOv8 엔진 → 메타 → 가사OCR → MusicXML 조립.
  - `ScoreUnderstandingAdapter`가 `OmrPort` 구현 — 오케스트레이터 무수정.
  - 버그 수정: PaddleOCR 포맷(`r[0]`→`r[1][0]`), 가사 인덱스(Rest 건너뜀), 베이스 클레프 교번.
- **MD 파일 체계 재구성** — `docs/superpowers/` 제거, `ARCHITECTURE.md` → `CLAUDE.md` 통합, `raw/project_start.md` 추가(범용 개발 방법론 + SDD 실제 루프 + Q&A 핵심 결정 기록).
- **다음:** Plan 1B 브레인스토밍 → YOLOv8 모델 학습.

### 2026-06-19 (OMR 심층 진단 + DL-OMR 재설계 방향 확정)
- **OMR 심층 진단** — MusicXML 파트 구조 직접 덤프 분석:
  - Audiveris 출력: Part 0(treble S+A), Part 1(bass T+B), 각 마디에 Voice1/Voice2 혼재.
  - 315장 소프라노 정답(52음) vs 검출(34음): 정답률 65%. **핵심 오류는 각 악절 첫 마디(m1,m6,m11,m16) 전체 누락** — 파서 문제가 아닌 Audiveris OMR 자체 미인식.
  - m2=D5(정답 A), m3=G5(정답 Bb) 등 피치 오인식도 다수.
  - 결론: **Audiveris 튜닝으로는 근본 해결 불가**. 재설계 필요.
- **DL-OMR 재설계 방향 확정** — 딥러닝 기반 OMR을 처음부터 개발. 찬송가·악보 앱 데이터로 지도학습. 헥사고날 아키텍처의 `OmrPort` 어댑터 교체점 활용.
- 설계 문서: [`docs/specs/design-why.md`](specs/design-why.md) 작성.

> 이력 갱신 규칙: 의미 있는 단계 완료/결정마다 위에 날짜 항목을 추가하고, 상단 **최종 갱신** 날짜를 바꾼다.

---

## 단계 정의 (요약)
```
1단계: 음표 → 모음 "우" → 믹싱            ← 완료
2단계: + 가사(텍스트/OCR) + 정렬 + 가사가창  ← 예정
트랙B: 교정데이터 → 한글 OCR 지도학습(오프라인)
```
