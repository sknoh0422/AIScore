# AIScore 로드맵 / 진행 상태

> **새 세션 진입점.** 이 프로젝트를 이어서 작업할 때 이 파일 하나만 열면 현재 상태와 다음 작업을 알 수 있다.
> 규약은 [CLAUDE.md](../CLAUDE.md), 전체 설계는 [설계 문서](superpowers/specs/2026-06-16-aiscore-design.md).

**최종 갱신:** 2026-06-18 (3차)

---

## 새 세션 시작 방법
1. `CLAUDE.md`는 자동 로드된다(프로젝트 규약).
2. 이 `docs/ROADMAP.md`를 읽어 현재 상태/다음 작업을 파악한다.
3. 진행 중 단계의 계획서(아래 링크)를 열어 미체크 태스크부터 이어간다.
4. 환경: `conda activate`가 비대화형 셸에서 실패하면 `/opt/miniconda3/envs/aiscore/bin/python` 절대경로 사용.

---

## ✅ 완료
- **프로젝트 설계 확정** — [설계 문서](superpowers/specs/2026-06-16-aiscore-design.md) (헥사고날, 1/2단계 로드맵, 트랙B)
- **CLAUDE.md** — 이중 오케스트레이션·레이어·라우팅·병렬화·절대규칙 20
- **스캐폴딩** — backend/frontend/training 구조, 동결된 `backend/app/domain/ports.py`
- **1단계 파이프라인 (image→OMR→SATB→모음"우"→믹싱)** — main 통합 완료, 단위 테스트 16 passed
  - 계획: [1단계 계획](superpowers/plans/2026-06-16-stage1-vowel-choir.md)
  - 구현: OMR(oemer)·파싱(music21)·SVS(VowelSynth)·믹싱 어댑터 + 오케스트레이터(4성부 병렬) + FastAPI 잡 API
- **Audiveris OMR 스테이지 (image→Audiveris→N성부)** — main 통합 완료, 단위 24 passed + E2E(315.JPG→choir.wav 18s) 검증
  - 계획: [Audiveris 계획](superpowers/plans/2026-06-17-audiveris-omr.md)
  - 구현: 전처리(업스케일) + `audiveris_adapter`(JDK25 배치) + `part×voice` 무손실 파서 + 존재 성부만 합성 + 업로드 검증. 실제 SATB는 트레블/베이스 2성부 가이드(완전 4성부는 교정 영역).
- **품질 개선 5종** — 33 passed, main 통합 완료 (`716cad9`)
  - ParseError 추가 + 파서 0-파트 방어 / 업로드 OOM 방어(`read(_MAX_BYTES+1)`) / 믹서 스테레오→모노 변환+samplerate 수정 / Store 격리(root 파라미터+reset, conftest autouse) / test_ports.py 포트 계약 테스트 5종 / pyproject.toml integration 마크 기본 제외
- **프론트엔드 (Next.js + OSMD)** — main 통합 완료 (`924a282`)
  - Next.js 15 + Tailwind v4 + TypeScript 5. 업로드 홈(드래그&드롭) → 잡 페이지(2초 폴링+진행 바+오디오 플레이어+OSMD 악보 렌더)
  - 백엔드 추가: CORS, score_path 추적, `/audio` · `/score` FileResponse 엔드포인트
  - 실행: `uvicorn app.main:app --reload` (포트 8000) + `npm run dev` (포트 3000)

## ⏳ 진행 중
- **feat/vocal-quality** — 4성부 화음 분리 + 성악 합성 개선. 커밋 `df2e363`. main 미머지.
- **모바일 앱 구현** — 계획서 작성 완료([2026-06-18-mobile-app.md](superpowers/plans/2026-06-18-mobile-app.md)), Task 1부터 서브에이전트 실행 예정.

## ⏳ 대기 / 검증 필요
- **고해상도 악보 OMR 검증** — 315.JPG 저해상도(500×777px)로 음표 커버리지 29%, 피치 정확도 27% 확인. 300 DPI 스캔본 업로드 후 재검증 필요.
- **프론트엔드 브라우저 실증** — Next.js 웹 앱 실제 악보 업로드 → 음원 재생 확인 필요.

## 📋 예정 (우선순위순)
- **모바일 앱 (React Native + Expo)** — 계획서 완료. 백엔드 API 확장(Task 1~2) → 모바일 화면(Task 3~10). [계획서](superpowers/plans/2026-06-18-mobile-app.md)
- **2단계 가사** — 가사 소스(텍스트 입력 기본/OCR 보조) + 음절↔음표 정렬 + 가사 가창 SVS 어댑터.
- **L4 교정 로깅** — 교정 결과를 (이미지영역, 오답, 정답) 라벨로 누적(플라이휠).
- **트랙 B(오프라인)** — 누적 라벨로 한글 OCR 지도학습(`training/`).

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

### 2026-06-18 (성악품질개선 + OMR검증 + 모바일설계)
- **4성부 화음 분리** (`music21_parser.py`) — Part별 chord 상단/하단 분리로 S/A/T/B 추출. verovio+cairosvg로 성부별 SVG/PNG 악보 이미지 생성 및 시각 비교.
- **성악 합성 품질 개선** (`vowel_synth_adapter.py`) — 3배음 사인파 → 성부별 배음(5~7개)+비브라토(5.5Hz)+숨소리+어택/릴리즈.
- **OMR 정확도 실측 검증** — 315.JPG(500×777px 촬영본) 원본 찬송가 음표와 1:1 비교: 음표 커버리지 29%(15/51), 피치 정확도 27%(4/15). 근본 원인 = 저해상도. 고해상도 스캔 재검증 예정.
- **모바일 앱 설계 확정** — iOS/Android 공통 React Native+Expo 채택. 화면: 홈(촬영/선택) → 처리중(단계폴링) → 플레이어(악보+파트선택+동기재생). 파트별 음원 선택 재생(expo-av 멀티트랙) + OSMD 실시간 하이라이팅(WebView+postMessage+timing.json) 설계.
- **timing.json API 설계** — 성부별 음표 시작/종료 시각 메타데이터. 백엔드 Task 1~2, 모바일 Task 3~10 계획서 완료.
- `feat/vocal-quality` 커밋 `df2e363` (main 미머지).

> 이력 갱신 규칙: 의미 있는 단계 완료/결정마다 위에 날짜 항목을 추가하고, 상단 **최종 갱신** 날짜를 바꾼다.

---

## 단계 정의 (요약)
```
1단계: 음표 → 모음 "우" → 믹싱            ← 완료
2단계: + 가사(텍스트/OCR) + 정렬 + 가사가창  ← 예정
트랙B: 교정데이터 → 한글 OCR 지도학습(오프라인)
```
