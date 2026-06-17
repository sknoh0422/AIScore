# AIScore 로드맵 / 진행 상태

> **새 세션 진입점.** 이 프로젝트를 이어서 작업할 때 이 파일 하나만 열면 현재 상태와 다음 작업을 알 수 있다.
> 규약은 [CLAUDE.md](../CLAUDE.md), 전체 설계는 [설계 문서](superpowers/specs/2026-06-16-aiscore-design.md).

**최종 갱신:** 2026-06-17

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

## ⏳ 대기 / 검증 필요
- **OMR 실측 검증 완료 (2026-06-17)** — `온맘다해.png`(단성부) oemer 정상 ✅ / `315.JPG`(밀집형 SATB) **oemer 크래시**(`assert track_nums == 2` → 검출 3) ❌. 결론: 실제 SATB엔 oemer 부적합 → **Audiveris 필요**.
- **GitHub push** — `main`을 origin에 푸시(데스크탑 앱 또는 인증된 터미널).

## 📋 예정 (다음 후보, 각각 별도 spec→plan)
- **★ OMR 엔진 교체: Audiveris 어댑터 (진행 중, 후보 조사 완료·채택)** — oemer가 SATB(`315.JPG`)에서 크래시 → `stages/omr/audiveris_adapter.py` 구현(Java/JVM 필요, OmrPort). 함께 파서를 **staff×voice** 기준으로, 오케스트레이터를 **OMR 실패·N성부**에 견고하게 보강. SMT++는 백로그.
- **프론트엔드** — Next.js + OSMD: 업로드·잡 상태·악보 렌더·교정 에디터.
- **2단계 가사** — 가사 소스(텍스트 입력 기본/OCR 보조) + 음절↔음표 정렬(slur/tie/절) + 가사 가창 SVS 어댑터.
- **L4 교정 로깅** — 교정 결과를 (이미지영역, 오답, 정답) 라벨로 누적(플라이휠).
- **트랙 B(오프라인)** — 누적 라벨로 한글 OCR 지도학습(`training/`).
- **품질 개선(1단계 리뷰 후속, IMPORTANT)** — 파트<4 방어(파서), 업로드 크기 제한, 믹서 스테레오 mix-down, 테스트 store 격리, `test_ports.py` 포트 계약 테스트 채우기.

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

> 이력 갱신 규칙: 의미 있는 단계 완료/결정마다 위에 날짜 항목을 추가하고, 상단 **최종 갱신** 날짜를 바꾼다.

---

## 단계 정의 (요약)
```
1단계: 음표 → 모음 "우" → 믹싱            ← 완료
2단계: + 가사(텍스트/OCR) + 정렬 + 가사가창  ← 예정
트랙B: 교정데이터 → 한글 OCR 지도학습(오프라인)
```
