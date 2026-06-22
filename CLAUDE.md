# CLAUDE.md — AIScore 프로젝트 헌법

> 세션 시작: [docs/ROADMAP.md](docs/ROADMAP.md) 먼저 읽어 현재 상태/다음 작업 파악.

---

## 1. 프로젝트

**AIScore** = SATB 찬송가 악보 이미지 → AI 합창 WAV / MusicXML 변환 웹·모바일 서비스.

**파이프라인:** `이미지 → OMR → 파싱(SATB분리) → SVS(성부별 가창) → 믹싱 → 합창 WAV`

| 단계 | 내용 | 상태 |
|------|------|------|
| 1단계 | 가사 무시, 모음"우" 합창 → 연습 가이드 트랙 | ✅ 완료 |
| 2단계 | 가사(텍스트/OCR) + 음절↔음표 정렬 + 가사 가창 | 예정 |
| 트랙B | 교정 데이터 → 한글 OCR 지도학습(오프라인) | 예정 |

**스택:** FastAPI(Python 3.10, conda `aiscore`, MPS) · Next.js+OSMD · React Native+Expo

---

## 2. 아키텍처 — 헥사고날(포트&어댑터)

의존성 단방향: `api → orchestration → stages → domain`

```
┌─────────────────────────────────────────────────┐
│ L1  API/Gateway       backend/app/api/           │  엔드포인트, Pydantic 스키마
├─────────────────────────────────────────────────┤
│ L2  Orchestration     backend/app/orchestration/ │  파이프라인 조율, 잡 상태, SVS 병렬
├─────────────────────────────────────────────────┤
│ L3  Stages(어댑터)    backend/app/stages/        │  OMR·파싱·SVS·믹싱 — 교체점
├─────────────────────────────────────────────────┤
│     Domain            backend/app/domain/        │  순수 Score 모델 + ports.py (Protocol)
└─────────────────────────────────────────────────┘
     L4  Correction     backend/app/corrections/      교정→라벨 플라이휠
     L5  Storage        backend/app/storage/          파일·잡 메타
     —   Core(횡단)     backend/app/core/             config · device · errors
     R1  Training       training/                     OCR 지도학습(서빙 경로 밖)
```

**어댑터 교체점 (OmrPort):**

| 포트 | 현재 어댑터 | 차후 교체 |
|------|-----------|---------|
| `OmrPort` | `AudiverisAdapter` (65% 정확도) | **DL-OMR 어댑터** (YOLOv8 → SMT++) |
| `SvsPort` | `VowelSynthAdapter` (모음"우") | `LyricSingingAdapter` (2단계) |
| `ScoreParserPort` | `Music21Parser` | — |

---

## 3. 잡 상태 모델

```
queued → omr → parsing → [lyric → align] → synth → mixing → done
                                                           ↘ failed
```
`[lyric → align]` 2단계에만 활성. 단계 실패 = `failed`(단계+원인) 즉시 표면화.

---

## 4. 에이전트 라우팅

| 파일 경로 | 에이전트 |
|----------|---------|
| `api/ orchestration/ storage/ corrections/**` | python-reviewer + fastapi-reviewer |
| `stages/svs\|mixing/**` | python-reviewer + performance-optimizer |
| `stages/omr\|parsing\|lyrics/**` | python-reviewer |
| `domain/**` | python-reviewer + type-design-analyzer |
| `frontend/**` | react-reviewer + typescript-reviewer |
| `training/**` | mle-reviewer |
| 외부 입력 경로 포함 모든 변경 | + security-reviewer **(필수)** |
| 머지 전 모든 변경 | code-reviewer + superpowers:requesting-code-review |

도구: 계획=`superpowers:writing-plans` · 탐색=`Explore` · 디버깅=`superpowers:systematic-debugging`

---

## 5. 병렬화 원칙

1. `ports.py` 동결 전 `stages/` 구현 병렬 금지
2. 동결 후 독립 모듈 병렬 (omr ∥ mixer ∥ storage)
3. frontend↔backend: API 스키마 합의 후 병렬
4. 공유 파일 동시 수정 금지 (또는 git worktree 격리)
5. 리뷰는 다음 구현과 병렬 가능
6. **수직 슬라이스 우선** — 1단계 경로 끝까지 동작 후 폭 확장

**절대 순서:** `계획 → ports.py 동결 → TDD → 리뷰 게이트 → 검증 → 통합`

---

## 6. 절대 규칙

**환경**
1. Python: conda `aiscore`(py3.10). 경로=`pathlib`, 디바이스=`core/device.py`(mps→cuda→cpu)
2. 개발·검증: macOS Apple Silicon(MPS). 다중 OS 이식성 설계 목표 — OS 종속 가정 금지
3. Bash 첫 명령: Fact-Forcing 게이트 준수

**아키텍처**
4. `domain/`에 torch·fastapi·music21 import 금지 (순수 Python)
5. 도메인/오케스트레이터는 `ports.py` 경유만 — 구체 구현 직접 import 금지
6. `ports.py` 동결 전 stage 구현 금지
7. 새 외부 엔진 = 새 어댑터 파일 추가 (기존 코드 수정 아님)

**프로세스·품질**
8. TDD: 구현 전 실패 테스트 먼저. 도메인·정렬·믹싱은 단위테스트 필수
9. 머지 전 리뷰 게이트 필수. 통과 없이 "완료" 선언 금지
10. 검증 없는 완료 주장 금지 — 테스트/실행 출력으로 증명
11. 버그·예외: 추측 수정 금지 → systematic-debugging
12. 조용한 실패 금지: 단계 실패 = 잡 상태 `failed`(단계+원인)

**데이터·안전**
13. `data/`·모델·대용량 WAV 커밋 금지
14. 외부 입력 경로 변경 시 `security-reviewer` 필수 (traversal·파일타입·크기)
15. L4 라벨: 원본 분리, 개인식별자 미포함
16. 외부 전송/공개: 명시 승인 전 금지

**단계·범위**
17. 1단계 스코프 고정: 음표→"우"→믹싱. 가사=`[2단계]`(YAGNI)
18. 수직 슬라이스 우선
19. `training/`(트랙B): 서빙 요청 경로 진입 금지
20. 응답·문서·주석: 한국어 기본
