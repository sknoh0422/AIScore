# 설계: homr OMR 어댑터 채택 (Audiveris → homr 최소 스위치)

**작성:** 2026-07-07 · **상태:** 설계 승인 대기
**관련:** [ROADMAP](../ROADMAP.md) OMR 경로 #3 · [CLAUDE.md](../../CLAUDE.md) 규칙 A7/§5

---

## 1. 목표와 배경

**전체 목표:** 이미지 → **높이+리듬이 맞는 4부(SATB) 악보** → 합창 WAV / MusicXML.

**이번 스펙 범위(수직 슬라이스):** 실행 중인 파이프라인의 OMR 엔진을 Audiveris(65%)에서
**사전학습 homr**로 전환하여, homr 출력으로 **실제 4성부 가이드가 끝까지 나오게** 한다.

**근거(기술선택 방법론 적용):**
- 전체 목표 기준으로 후보의 **발전가능성**을 평가 → homr는 딥러닝(트랜스포머, repo에 `training/` 존재)이라
  파인튜닝·후처리로 개선 천장이 높음. Audiveris는 규칙 기반이라 "튜닝으로 근본 해결 불가"(ROADMAP L172).
- 따라서 발전가능성 없는 Audiveris 재측정은 생략하고 homr로 확정.

**중요 사실 — 88%의 정체:** 기준선 88%는 **피치 멀티셋(bag) F1**이며 성부·순서·리듬을 무시한다.
즉 "음 높이 재료가 대체로 맞다"는 신호일 뿐, **4부 분리·리듬 정확도는 미측정**이다.
(hymn001: homr 132음 ≈ GT 136음 → 안쪽 성부 재료는 화음 형태로 대부분 존재 → 4부 분리 원천 가능.)

---

## 2. 결정 요약

| 항목 | 결정 | 이유 |
|---|---|---|
| OMR 엔진 | **homr 채택** | 발전가능성(파인튜닝) + 피치 재료 우세 |
| 통합 방식 | **subprocess CLI** | homr는 Python 3.11 별도 venv + ONNX 번들, aiscore는 3.10 → 프로세스 격리. 기존 Audiveris 어댑터와 동일 패턴 |
| Audiveris 처리 | **그대로 두고 스위치만** | 최소 변경·되돌리기 용이. 죽은 코드는 남지만 무해 |
| 파서 | **기존 `Music21Parser` 확장** | homr 1-part/2-staff 구조 지원 추가(Audiveris 2-part도 유지) |

---

## 3. 아키텍처 (헥사고날 유지)

```
이미지 → [HomrAdapter(OmrPort)] → homr MusicXML
       → [Music21Parser(ScoreParserPort)] → SATB Score → SVS(4성부 병렬) → Mixer → 합창 WAV
```

오케스트레이터(`Stage1Orchestrator`)는 **무수정**. 배선(`api/routes/jobs.py`)에서 주입 어댑터만 교체.

### homr 실행 계약 (확인됨)
- 실행: `<homr_repo>/.venv/bin/homr <image>` (positional). ONNX CoreML/CPU 자동 선택.
- 출력: 입력 옆에 `<stem>.musicxml` 생성(`replace_extension`). teaser/debug는 `--debug`시에만.
- 구조: 단일 `<part-name>Piano` + 2보표(staff1=G clef 트레블, staff2=F clef 베이스), 화음은 voice에 적재.

---

## 4. Stage A — HomrAdapter (신규, OmrPort)

**파일:** `backend/app/stages/omr/homr_adapter.py` (신규, 규칙 A7)

**동작:**
1. 입력 이미지 존재 검증 → 없으면 `OmrError`.
2. `work_dir`에 입력 복사(또는 심볼릭) → homr가 출력을 그 옆에 쓰도록.
3. `subprocess.run([homr_bin, str(img)])` 실행 (환경변수 불필요, JDK 무관).
4. `<stem>.musicxml` 존재+returncode 0 확인 → 실패 시 `OmrError`(단계+원인, stderr 말미). **크래시 = 잡 `failed`**(규칙 12). → ROADMAP #5(hymn040·177) 흡수.
5. 생성된 `.musicxml` 경로 반환.

**config 추가:** `core/config.py`에 `homr_bin()` (기본 `<repo>/../homr/.venv/bin/homr`, 환경변수 `AISCORE_HOMR_BIN` override). 경로순회/미설치 방어.

**보안(규칙 14):** 입력은 이미 업로드 검증(content-type/크기/실이미지)을 거친 경로. 어댑터는 경로만 subprocess에 전달하되 셸 미경유(`shell=False`, 리스트 인자)로 인젝션 차단.

---

## 5. Stage B — 파서 확장 (핵심)

**파일:** `backend/app/stages/parsing/music21_parser.py` (확장)

**문제:** 현재 `_is_vocal_part()`가 파트명에 "Piano"가 있으면 **제외** → homr 단일 "Piano" 파트가 통째로 버려져 성부 0개 → `ParseError`.

**해결:**
- **구조 인지 분기:** 파트가 1개이고 보표(staff)가 2개면 homr 모드로 처리 — staff1 화음 → S(상)/A(하), staff2 화음 → T(상)/B(하). 파트 2개면 기존 Audiveris 경로 유지.
- "Piano" 필터는 homr 모드에서 **미적용**(homr의 Piano는 성악 내용).
- 기존 `_split_two_voices`(화음 상/하 분리) 재사용, staff별로 적용.

**성공 기준:** homr 출력 → S/A/T/B 4성부가 채워진 `Score` 반환. 존재 성부만 합성하는 오케스트레이터 로직과 정합.

---

## 6. Stage C — 측정 확장 (진단, 후속)

이번 슬라이스 이후. `eval_baseline.py`에 **리듬(duration 일치·마디합=박자표 유효율) + 성부배정(S/A/T/B 각 F1)** 지표 추가 → homr의 리듬·4부 정확도 실측 → Stage D 후처리 우선순위 근거.

---

## 7. Stage D/E — 후처리·교정 (로드맵, 범위 밖)

- **D 후처리:** 조표 후처리(Ab→Eb 교정) / 리듬 정규화(마디합 강제) / 찬송가 구조 프라이어(동음리듬·알려진 조·박자). 각각 측정 델타로 채택.
- **E 교정 에디터(L4) + 파인튜닝:** 잔여 오류 사람 교정 → 플라이휠 → homr 파인튜닝.

---

## 8. 테스트 계획 (TDD, 규칙 8)

- `test_homr_adapter.py`: ①없는 이미지 → OmrError ②homr 미설치 경로 → OmrError ③(integration) 실제 이미지 → .musicxml 생성. subprocess는 단위테스트에서 모킹.
- `test_ports.py`: `HomrAdapter`가 `OmrPort` 만족(runtime_checkable).
- 파서: homr 픽스처(`fixtures/satb_homr.musicxml`, 실제 homr 출력 1곡) → 4성부 분리 검증. 기존 Audiveris 픽스처 테스트도 계속 통과(회귀).
- 배선: jobs.py가 HomrAdapter 주입 확인.

---

## 9. 리스크

| 리스크 | 대응 |
|---|---|
| homr 재로딩 오버헤드(호출당 수~수십초) | 1단계 단건 처리엔 허용. 병목 시 Stage 후속에서 상주 서비스(C안) 검토 |
| 외부 clone 경로 의존(`../homr`) | config override + 미설치 시 명확한 OmrError |
| 파서 4부 분리 품질 미검증 | Stage C 진단으로 수치화 후 D에서 개선 |
| 88%는 피치가방 — 리듬/성부 미보증 | 스펙에 명시. "88%≠4부합창" 전제로 진행 |

---

## 10. 범위 밖 (YAGNI)

- Audiveris 코드/vendor/테스트 삭제 (그대로 둠)
- oemer·score_understanding 어댑터 정리 (별도 논의)
- 조표/리듬 후처리, 파인튜닝, 교정 에디터 (Stage D/E, 후속 스펙)
- 상주 마이크로서비스화 (C안, 병목 확인 시)
