# AIScore 로드맵 / 진행 상태

> **새 세션 진입점.** 이 프로젝트를 이어서 작업할 때 이 파일 하나만 열면 현재 상태와 다음 작업을 알 수 있다.
> 규약은 [CLAUDE.md](../CLAUDE.md), 전체 설계는 [설계 문서](specs/2026-06-16-aiscore-design.md).

**최종 갱신:** 2026-07-09 (9차)

---

## 새 세션 시작 방법
1. `CLAUDE.md`는 자동 로드된다(프로젝트 규약).
2. 이 `docs/ROADMAP.md`를 읽어 현재 상태/다음 작업을 파악한다.
3. 진행 중 단계의 계획서(아래 링크)를 열어 미체크 태스크부터 이어간다.
4. 환경: `conda activate`가 비대화형 셸에서 실패하면 `/opt/miniconda3/envs/aiscore/bin/python` 절대경로 사용.

---

## ✅ 완료
- **프로젝트 설계 확정** — [설계 문서](specs/2026-06-16-aiscore-design.md) (헥사고날, 1/2단계 로드맵, 트랙B)
- **CLAUDE.md** — 이중 오케스트레이션·레이어·라우팅·병렬화·절대규칙 20
- **스캐폴딩** — backend/frontend/training 구조, 동결된 `backend/app/domain/ports.py`
- **1단계 파이프라인 (image→OMR→SATB→모음"우"→믹싱)** — main 통합 완료, 단위 테스트 16 passed
  - 계획: [1단계 계획](plans/2026-06-16-stage1-vowel-choir.md)
  - 구현: OMR(oemer)·파싱(music21)·SVS(VowelSynth)·믹싱 어댑터 + 오케스트레이터(4성부 병렬) + FastAPI 잡 API
- **Audiveris OMR 스테이지 (image→Audiveris→N성부)** — main 통합 완료, 단위 24 passed + E2E(315.JPG→choir.wav 18s) 검증
  - 계획: [Audiveris 계획](plans/2026-06-17-audiveris-omr.md)
  - 구현: 전처리(업스케일) + `audiveris_adapter`(JDK25 배치) + `part×voice` 무손실 파서 + 존재 성부만 합성 + 업로드 검증. 실제 SATB는 트레블/베이스 2성부 가이드(완전 4성부는 교정 영역).
- **품질 개선 5종** — 33 passed, main 통합 완료 (`716cad9`)
  - ParseError 추가 + 파서 0-파트 방어 / 업로드 OOM 방어(`read(_MAX_BYTES+1)`) / 믹서 스테레오→모노 변환+samplerate 수정 / Store 격리(root 파라미터+reset, conftest autouse) / test_ports.py 포트 계약 테스트 5종 / pyproject.toml integration 마크 기본 제외
- **프론트엔드 (Next.js + OSMD)** — main 통합 완료 (`924a282`)
  - Next.js 15 + Tailwind v4 + TypeScript 5. 업로드 홈(드래그&드롭) → 잡 페이지(2초 폴링+진행 바+오디오 플레이어+OSMD 악보 렌더)
  - 백엔드 추가: CORS, score_path 추적, `/audio` · `/score` FileResponse 엔드포인트
  - 실행: `uvicorn app.main:app --reload` (포트 8000) + `npm run dev` (포트 3000)
- **Score Understanding Pipeline (DL-OMR 5모듈)** — main 머지 완료 (`e50e493`, 2026-06-22), 88 passed
  - 계획: [파이프라인 계획](plans/2026-06-19-score-understanding-pipeline.md)
  - 설계: [파이프라인 설계](specs/2026-06-19-score-understanding-pipeline-design.md)
  - 구현: 전처리 → 레이아웃 분석 → YOLOv8 OMR 엔진 → 메타 추출 → 가사 OCR(PaddleOCR) → MusicXML 조립 → `ScoreUnderstandingAdapter(OmrPort)`
  - 현재 상태: YOLOv8 모델 미학습(더미 패스스루). 다음 단계 = 모델 학습(Plan 1B)
- **MD 파일 체계 재구성** — `docs/superpowers/` 제거, `docs/plans/` · `docs/specs/` · `raw/project_start.md` 정착
- **homr 사전학습 OMR 기준선 실측 (645곡)** — 브랜치 `feat/omr-baseline-eval`(main 미머지), `f5d7696`
  - GT: `nwc2xml`로 새찬송가 645곡 정답 MusicXML 생성(001 XML 품질 버그 12종 수정 포함).
  - 평가: `training/scripts/eval_baseline.py` — bag-of-notes P/R/F1 + 성부별 SER.
  - 결과: 실행 성공 **643/645**(실패 hymn040·hymn177), 평균 피치 **F1 83.2%**(중앙값 89.1%, F1≥0.9 = 46%). 10곡 예비 실측은 F1 88.1%.
  - 지배적 오류 = **조표 오인식(♭ 과다 → 반음 하향 전조)**. ±2반음 최적 보정 시 평균 **F1 88.3%**(오라클 상한).
  - **전략 결론:** Audiveris(65%) 대비 사전학습 homr가 우세 → 자체 YOLOv8 처음부터 학습이 아니라 **사전학습 homr + 조표 후처리 + 표적 파인튜닝** 경로로 전환.
- **조표 판정 + GT(정답지) 교정 → 검증 baseline 88.0%** — `feat/omr-baseline-eval`
  - 조표 불일치 102곡을 웹 판정 도구(`training/scripts/key_adjudicator/`)로 사람이 이미지 대조 판정.
  - **발견: 102곡 중 53곡은 homr가 옳고 정답지(GT)가 틀림**(NWC→XML 변환 시 오조). → 83.2%는 GT 오류로 homr를 부당하게 깎은 값.
  - GT 오류 곡을 실제 조로 이조(移調) — 단, **이조가 F1을 실제 개선할 때만 채택**(겉보기 조표차 8곡은 원본 유지, 손상 0곡).
  - **재채점: 평균 F1 83.2% → 88.0%**(50곡 개선, F1≥0.9 곡수 296→332). 오라클(88.3%)과 근사 = 오라클 이득 대부분이 homr 오류가 아닌 GT 오류였음을 확인. 사람 검증 라벨: `training/baseline_eval/key_adjudication.json`.
  - **남은 진짜 homr 오류 44곡** = 조표 플랫 과소인식(Ab→Eb 등) → 표적 파인튜닝 타깃.

## ⏳ 대기 / 검증 필요
- **고해상도 악보 OMR 검증** — 315.JPG 저해상도(500×777px)로 소프라노 검출 34/52음(65%), 4개 마디 전체 누락. 300 DPI 스캔본으로 재검증 필요.

## 📋 예정 (우선순위순)

### 🔴 최우선: OMR 엔진 = 사전학습 homr 채택 경로

> **전략 전환(2026-07-07):** 645곡 기준선 실측 결과, 사전학습 homr가 F1 83.2%(조표 보정 시 88.3%)로 Audiveris(65%)를 크게 앞섬. 자체 YOLOv8을 처음부터 학습(구 Plan 1B)하는 대신, **사전학습 homr를 `OmrPort` 어댑터로 채택 → 조표 후처리 → 표적 파인튜닝** 순으로 정확도를 끌어올린다.

**목표 정확도:** 피치 F1 ≥ 95%, 조표 오인식 0, 마디 전체 누락 0

**다음 태스크 (브레인스토밍 → 설계 → 계획 필요):**
1. `feat/omr-baseline-eval` 정리 → main 머지 (대용량 산출물 gitignore 정책 포함)
2. ✅ **조표 판정 + GT 교정** — 완료(검증 baseline 88.0%). GT 오류 50곡 이조 교정, homr 오류 44곡 식별.
3. ✅ **homr 어댑터** — 사전학습 homr를 `HomrAdapter(OmrPort)`로 래핑, 파이프라인 OMR 엔진 Audiveris→homr **최소 스위치** 완료(`feat/homr-adapter`). subprocess 통합, 파서 "Piano" 폴백 + 다중 Voice offset 정렬 버그 수정. 단위 100 passed, E2E 4성부 생성 실측. Audiveris 자산은 유지(스위치만).
   - ✅ **Stage C — homr 4부 정확도 실측 완료** (`training/scripts/eval_satb.py`, GT=`분리_keyfix`, 642곡 채점·실패 0). 실제 `Music21Parser`로 GT·homr 둘 다 SATB 파싱 후 성부별 대조.
     - **결과(성부별 피치 F1 / 리듬 SER):** S 0.804/0.345 · A **0.800**/0.372 · T 0.826/0.332 · B 0.856/**0.411**(n=623). 산출물 `eval_satb_homr_full.json`.
     - **핵심:** 성부배정 F1 **80~86%** — 전체 피치가방 88%보다 낮음(88%는 낙관적 상한 확증). 안쪽 성부(A/S)가 약함. 리듬 SER **33~41%**(그간 미측정) — **리듬이 성부배정보다 큰 병목**(특히 Bass는 피치 최고인데 리듬 최악).
     - 남은 검증: 성부 정합 caveat(GT 4파트↔homr 2보표 S/A/T/B 규약 일치), Bass 누락 ~19곡 원인.
   - **정확도 개선 조사(2026-07-08):**
     - ①파서 성부배정 개선 = **막다른 길**. 오배정 격차 3.4%p는 진짜 성부교차 모호성 → voice-leading 실험 델타 **+0.000**(비파괴 측정). 프로덕션 미변경.
     - ②**입력 화질 = 유력 병목 + 측정 타당성 경고.** 입력 PNG는 NWC 렌더 산출물인데 **너비 800px** → homr가 **1920px로 2.4× 흐리게 업스케일**(정보 미증가). **현 벤치마크(88%/Stage C 80~86%)가 homr를 과소평가할 가능성** — 12%p 인식손실이 homr 한계가 아니라 저해상도 입력 탓일 수 있음.
     - **재렌더 실험 시도→막힘(2026-07-08):** verovio+cairosvg로 분리_keyfix를 저/고해상 래스터 렌더해 비교 시도 → homr가 verovio **조판 스타일**을 거의 못 읽어 F1 0.13~0.16 붕괴(원본 0.80~0.86). "해상도"가 아니라 "조판"이 교란변수 → 무효. **verovio/MuseScore 재시도 금지**(조판이 원본 새찬송가와 달라 homr 미인식).
     - **막힌 이유:** 원본 800px PNG는 NWC(NoteWorthy 독점)→저DPI 렌더 산출물. 같은 파이프라인 고DPI 재렌더가 mac에서 불가. **해상도 가설은 현재 도구로 검증 불가** → 원본 고해상도 소스 확보 or 실제 사용자 사진 벤치마크가 필요.
     - **다운스케일 민감도 테스트(2026-07-08) → 해상도 병목 아님 확정.** 기존 800px PNG를 400px로 낮춰 homr 재인식: 성부F1 0.963→0.945(델타 **−0.019**). 해상도에 거의 둔감. (caveat: 표본 hymn001~005는 쉬운 곡 F1 0.96대). 어차피 현재 파일로 native 고해상 생성 불가 → **해상도는 실행 가능 레버 아님, 종결.**
     - **확정 결론:** 12%p 인식손실 = 해상도 아님 = **homr의 새찬송가 조판·표기 인식 한계**. → **③ 파인튜닝(Stage E)이 현재 파일로 가능한 유일한 실질 레버.** 특히 조표 플랫 과소인식 44곡 systematic 오류가 타깃.
   - **Stage D (리듬)** — 리듬 정규화(마디합=박자표, 양자화, 동음리듬 프라이어). 단 ② 재렌더 후 리듬 SER도 재측정 필요(저해상도가 리듬 인식도 눌렀을 수 있음).
4. **표적 파인튜닝(Stage E)** — homr 오류 44곡의 지배 패턴 = **조표 플랫 과소인식**(Ab→Eb 등, 플랫 1~2개 누락). 플랫 조표(4~5개) 인식 강화가 핵심 타깃. + L4 교정 에디터 플라이휠.
   - ✅ **설계 스펙 확정**(`docs/specs/2026-07-08-homr-finetune-design.md`, 2026-07-09 코드검증 리뷰). 결정 ①MuseScore 렌더(진짜 게이트=NWC 전이 F1) ②지표=SATB 성부F1 ③1차 `--fine`(lift 헤드만) 확정.
   - ✅ **헤드 귀속 게이트 실행**(`head_attribution.py`, 642곡). 발음피치=pitch헤드+lift헤드 분해. **플랫 과소인식 46곡 = lift 헤드 지배 확정**(staff_F1 0.903 유지, sound_F1 0.809, gap 0.094) → `--fine` 정조준 맞음. **단 `--fine` 이론 상한=pitch헤드 0.903** → 목표 0.99는 `--fine`만으론 불가, **전체 파인튜닝 필수**. 저F1 집단은 pitch헤드가 병목(0.903→0.794).
5. 실패 케이스 분석 — hymn040·hymn177 실행 실패 원인 진단(homr 크래시는 `OmrError`→`failed`로 표면화됨)

> 구 Plan 1B(YOLOv8 자체 학습, DeepScores V2 사전학습)는 homr 채택으로 **보류**. Score Understanding Pipeline 코드(더미 패스스루)는 유지.

**설계 문서:** [DL-OMR 설계](specs/2026-06-19-dl-omr-design.md)

---

- **L4 교정 로깅** — 교정 결과를 (이미지영역, 오답, 정답) 라벨로 누적(DL 학습 데이터 플라이휠).
- **모바일 앱 (React Native + Expo)** — 계획서 완료. [계획서](plans/2026-06-18-mobile-app.md)
- **2단계 가사** — 텍스트 입력/OCR + 음절↔음표 정렬 + 가사 가창 SVS.

---

## 진행 이력 (날짜별)

### 2026-07-09 (Stage E 설계 확정 + 헤드 귀속 게이트)
- **파인튜닝 설계 스펙 리뷰·확정** — `../homr` 실코드 대조로 3결정 검증. `--fine`=`freeze_encoder+freeze_decoder+unfreeze_lift_decoder`(train.py:199-201, lr 1e-5) 확인. **결정 ③ 근거 정정:** 조표=rhythm헤드(동결)·lift=음표별 임시표(학습)로 서로 다른 헤드지만, 발음 피치=`pitch헤드+lift헤드`(music_xml_generator.py:626-629, 조표 토큰은 발음 미변경)이므로 우리 F1엔 `--fine`이 맞는 헤드. 결정 ①은 진짜 게이트를 NWC 전이 F1으로 상향, NWC-네이티브 학습을 Q2 이전 폴백 등록.
- **★ 무비용 사전 게이트 신설·실행**(`training/scripts/head_attribution.py`, 642곡) — 발음피치를 staff{step,oct}(pitch헤드)·sound{step,oct,alter}(pitch+lift)로 분해해 오류를 헤드에 귀속.
  - **플랫 과소인식 46곡 = lift 헤드 지배 확정**(staff_F1 0.903 유지·sound_F1 0.809·gap 0.094). 예 hymn373 staff 0.843/sound 0.393. → `--fine` 정조준 검증.
  - **`--fine` 이론 상한 = pitch헤드 F1 0.903.** 목표 0.99는 `--fine` 단독 불가 → **전체 파인튜닝 필수**(저F1 하위25%는 pitch헤드 0.903→0.794가 병목). 스펙 §2.2 기록.
- **Task 2 착수 — 파이프라인 빌딩블록 전부 검증(hymn001 수직 슬라이스):**
  - MuseScore 4.7.3 mac: **`-j` job 모드만 작동**(`-o`는 exit 40 실패). `out:[svg,musicxml]` 동시 export 성공. exit 134(크래시)나도 파일 정상 생성 → **파일 존재로 판정**.
  - `rsvg-convert` 2.62.3 설치(svg→png). homr venv에 **torch-CPU 설치**(토크나이저 의존).
  - **토크나이저는 MuseScore-export musicxml에만 동작**(원본 GT는 `Expected clefs` 에러) → 파이프라인=원본GT→MuseScore재export→토큰화. hymn001 라벨 `keySignature_-4`+`note_4 A4 b`(Ab) 정확 = 파인튜닝 lift 타깃 확인.
- **검증됨:** `convert_xml_and_svg_file`(homr) 재사용 = 토큰화+SVG위치+staff크롭+rsvg png+인덱스라인을 일괄 처리 → convert_saechan은 **얇은 드라이버**면 충분(MuseScore `-j` 배치 렌더 → 함수 호출 → train/heldout 분할).
- **⛔ 블로커(다음 착수점):** hymn001에서 **SVG 13마디 vs XML 12마디** 불일치 → crop 스킵(인덱스 0줄). 원인 = 우리가 원본 MusicXML을 직접 렌더해 convert_lieder의 **`.mscx` 전처리(`_make_staff_visible`/`_make_tuplet_visible`, 빈 보표 숨김 방지)를 건너뜀**. 정답 경로 = MusicXML→`.mscx` export→가시성 편집→재렌더(convert_lieder `create_formats` 경로). **추측 수정 금지 → 마디 카운트 불일치(픽업/보표수/헤더) systematic-debugging으로 규명 후 convert_saechan에 반영.**
- **다음:** convert_saechan.py 본구현(위 블로커 해결 = `.mscx` 전처리 경로 포함) → 5곡 수직슬라이스로 yield 측정 → 645 배치 → train/heldout 분할 → Task 3~4(번들·평가) → 4090 학습(`--fine` 1차 후 전체 파인튜닝 예약).

### 2026-07-08 (homr 어댑터 전환 — 파이프라인 OMR 엔진 교체)
- **의사결정** — 전체목표(높이+리듬 4부 악보) 기준 발전가능성으로 homr 확정. 88%는 피치 멀티셋(bag)이라 4부 분리·리듬은 미보증임을 명문화. Audiveris 65%는 딴 잣대(1곡 소프라노 검출)라 재측정 불필요·드롭. Audiveris 자산은 삭제 않고 스위치만.
- **설계·계획** — `docs/specs/2026-07-07-homr-adapter-design.md`(스펙), `docs/plans/2026-07-07-homr-adapter.md`(6태스크 TDD).
- **구현(`feat/homr-adapter`, 서브에이전트 주도 TDD)** — `config.homr_bin()` → `HomrAdapter(OmrPort)`(subprocess homr CLI, 실패=`OmrError`→`failed`) → 포트 계약 테스트 → 파서 "Piano" 폴백(필터 0줄시 해제) → 배선 교체(오케스트레이터 무수정). music21가 homr 2-staff를 2 PartStaff로 파싱 실측 반영.
- **버그 수정** — 파서 다중 Voice가 offset순 아닌 문서순 연접 → S/A(40박)>T/B(36박) 동기화 붕괴. `part.chordify()`로 offset 병합, 전 성부 37박 정렬. 성부 길이 정렬 회귀 테스트 추가.
- **검증** — 단위 **100 passed**, E2E 실측 hymn001 → soprano=38/alto=38/tenor=34/bass=34(정렬 후 길이 동등). 최종 전수 리뷰 GO.
- **다음** — Stage C(리듬·성부 지표로 4부 정확도 실측) → Stage D 후처리 → Stage E 파인튜닝.

### 2026-07-07 (조표 판정 + GT 교정 → 검증 baseline 88.0%)
- **조표 불일치 102곡** 웹 판정 도구 제작(`training/scripts/key_adjudicator/`, 데이터/셸/로직/스타일 분리) → 사람이 실제 악보 이미지와 대조해 homr vs GT 중 실제 조를 판정.
- **핵심 발견:** 102곡 중 **53곡은 GT(정답지)가 틀렸고 homr가 옳았음**(NWC→XML 변환 시 오조). 기존 83.2%가 GT 오류로 homr를 과소평가.
- **GT 교정:** 오류 곡을 실제 조로 이조하되 **F1 개선 시에만 채택**(원본 비파괴 `분리_keyfix/`, 겉보기 조표차 8곡 원본 유지, 손상 0). 재채점 **83.2%→88.0%**(50곡↑, F1≥0.9 296→332). 오라클(88.3%)과 근사.
- **남은 homr 오류 44곡** = 조표 플랫 과소인식 → 표적 파인튜닝 타깃 확정. 사람 검증 라벨 `key_adjudication.json` 확보.

### 2026-07-07 (homr 사전학습 OMR 기준선 실측 → 전략 전환)
- **GT 정답지 구축** — `nwc2xml`로 새찬송가 645곡 정답 MusicXML 생성. 001 XML 품질 버그 12종 수정(M7 수직/정렬 복원, 베이스 A♭3·D♭ 내림표 보정, Voice2 fill rest 제거 등) — `7014c3a`~`a06dc0c`.
- **평가 스크립트** — `training/scripts/eval_baseline.py`(bag-of-notes P/R/F1 + 성부별 SER). 10곡 예비 실측 F1 88.1% — `2283697`.
- **전곡 645 실측** — `f5d7696`. 실행 성공 643/645(실패 hymn040·hymn177), 평균 피치 **F1 83.2%**(중앙값 89.1%, F1≥0.9 = 46%).
  - 지배적 오류 = **조표 오인식(♭ 과다 → 반음 하향 전조)**. ±2반음 최적 보정 시 평균 **F1 88.3%**(53곡 +0.1 이상 개선, 보정 후 F1<0.6은 13곡뿐). 산출물: `eval_homr645.json`, `shift_analysis.json`.
- **전략 전환** — Audiveris(65%) 대비 사전학습 homr 우세 확인 → 구 Plan 1B(YOLOv8 자체 학습) 보류, **사전학습 homr 어댑터 + 조표 후처리 + 표적 파인튜닝** 경로로 확정.
- 상태: 브랜치 `feat/omr-baseline-eval` main 미머지. `score_images/`·`homr_full/` 등 대용량 산출물 gitignore 정책 정리 필요.

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
- 설계 문서: [`docs/superpowers/specs/2026-06-19-dl-omr-design.md`](superpowers/specs/2026-06-19-dl-omr-design.md) 작성.

> 이력 갱신 규칙: 의미 있는 단계 완료/결정마다 위에 날짜 항목을 추가하고, 상단 **최종 갱신** 날짜를 바꾼다.

---

## 단계 정의 (요약)
```
1단계: 음표 → 모음 "우" → 믹싱            ← 완료
2단계: + 가사(텍스트/OCR) + 정렬 + 가사가창  ← 예정
트랙B: 교정데이터 → 한글 OCR 지도학습(오프라인)
```
