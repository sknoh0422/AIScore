# CLAUDE.md — AIScore 프로젝트 헌법

> 이 파일은 Claude Code가 매 세션 로드하는 운영 규약이다.
> 상세 설계는 [설계 문서](docs/superpowers/specs/2026-06-16-aiscore-design.md) 참조.
> **이어서 작업하려면:** 현재 상태/다음 작업은 [docs/ROADMAP.md](docs/ROADMAP.md) 를 먼저 본다.

## 1. 프로젝트 요약

**AIScore** = 4성부 찬송가 악보(SATB) 이미지를 업로드하면, 악보를 인식·이해하여
각 성부를 AI 목소리로 노래시키고 합쳐 **AI 찬양대 합창 음원**을 생성하는
웹 기반 크로스플랫폼 서비스.

- **파이프라인:** `이미지 → OMR → music21 파싱(SATB 분리) → SVS(성부별 가창) → 믹싱 → 합창 WAV`
- **단계 로드맵:**
  - **1단계** (현재 스코프): 가사 무시, **모음 "우"** 로 합창 → 연습 가이드 트랙. 저위험.
  - **2단계**: 가사 추가 — 텍스트 입력(기본)/OCR(보조) + 음절↔음표 정렬 + 가사 가창 SVS.
  - **트랙 B** (오프라인): 교정 데이터로 한글 OCR 지도학습. 서빙과 분리.
- **스택:** Backend FastAPI(Python 3.10, conda `aiscore`, torch/MPS) · Frontend Next.js + OSMD.

## 2. 이중 오케스트레이션

이 프로젝트의 "오케스트레이터/에이전트/라우팅"은 두 층위를 동시에 의미한다.

- **런타임 오케스트레이션** (앱): `backend/app/orchestration/orchestrator.py` 가
  파이프라인 단계를 조율하고 SVS 4성부를 병렬 실행한다.
- **개발시간 오케스트레이션** (이 문서 §5): 메인 Claude 세션이 오케스트레이터로서
  작업을 전문 서브에이전트로 라우팅한다.

## 3. 레이어 (런타임)

헥사고날(포트&어댑터). 의존성은 **바깥→안 단방향**: `api → orchestration → domain`.

| | 레이어 | 위치 | 책임 |
|---|---|---|---|
| L1 | API/Gateway | `backend/app/api/` | 엔드포인트, Pydantic 스키마, 잡 생성/상태/결과 |
| L2 | Orchestration | `backend/app/orchestration/` | 파이프라인 조율, 잡 상태, SVS 병렬 |
| L3 | Pipeline Stages | `backend/app/stages/` | OMR·파싱·가사·정렬·SVS·믹싱 (어댑터) |
| — | Domain | `backend/app/domain/` | 순수 Score 모델 + 포트 인터페이스 |
| L4 | Correction/Dataset | `backend/app/corrections/` | 교정→라벨 누적 (플라이휠) |
| L5 | Storage | `backend/app/storage/` | 파일·잡 메타 |
| — | Core(횡단) | `backend/app/core/` | config · device · errors |
| R1 | Training(오프라인) | `training/` | OCR 지도학습 (서빙 경로 밖) |

교체점(어댑터)은 모두 `stages/` 안: OMR=`oemer_adapter`(1차)/`audiveris_adapter`(자리),
SVS=`vowel_synth_adapter`(1단계)/`lyric_singing_adapter`(자리), 가사=`text_input`/`ocr`(2단계).

## 4. 개발시간 에이전트 라우팅

작업/파일 경로별로 아래 에이전트로 라우팅한다 (구현 → 리뷰 게이트).

```
backend/app/api|orchestration|storage|corrections/**  → python-reviewer + fastapi-reviewer
backend/app/stages/svs|mixing/**                       → python-reviewer + performance-optimizer (+pytorch-build-resolver)
backend/app/stages/omr|parsing|lyrics/**               → python-reviewer
backend/app/domain/**                                  → python-reviewer + type-design-analyzer
frontend/**                                            → react-reviewer + typescript-reviewer  (빌드: react-build-resolver)
training/**                                            → mle-reviewer
* (파일 업로드/외부입력 경로 포함 변경)                → + security-reviewer (필수)
모든 코드 변경 (머지 전)                                → code-reviewer + superpowers:requesting-code-review
```
- 계획: `ecc:architect` / `Plan` / `superpowers:writing-plans`
- 탐색: `Explore` / `ecc:code-explorer`
- 디버깅: `superpowers:systematic-debugging` (추측 수정 금지)
- 구현: `superpowers:test-driven-development` (테스트 먼저)

## 5. 병렬화 원칙

1. **인터페이스 동결이 선결.** `domain/ports.py` 확정 전 `stages/` 구현 병렬 금지.
2. 동결 후 독립 모듈은 병렬 (omr_adapter ∥ mixer ∥ storage).
3. frontend ↔ backend 는 API 스키마 합의 후 병렬.
4. 공유 파일 동시 수정은 병렬 금지 (또는 git worktree 격리).
5. 리뷰는 다음 구현과 병렬.
6. **수직 슬라이스 우선** — 1단계 경로를 끝까지 동작시킨 뒤 폭 확장.

**절대적 순서:** `계획 → ports.py 동결 → TDD 구현 → 리뷰 게이트 → 검증 → 통합`

## 6. 절대 규칙 (깨지 않음)

**환경·도구**
1. Python은 conda 환경 `aiscore`(py3.10)에서만. `aiscore_env.yml`이 기준이나,
   의존성 해석기에 의한 전이 라이브러리 버전 자동 조정은 허용 — 직접(top-level)
   의존성만 명시 기록, 엄격한 핀 고정으로 싸우지 않는다.
2. 개발·검증은 macOS(Apple Silicon, MPS). 단 **다중 OS 이식성**을 설계 목표로 —
   OS 종속 가정 금지, 경로는 `pathlib`, 디바이스는 `core/device.py` 한 곳에서
   `mps→cuda→cpu`.
3. Bash 첫 명령 시 Fact-Forcing 게이트 준수.

**아키텍처**
4. 의존성 단방향. `domain/` 에 torch·fastapi·music21 import 금지(순수 Python).
5. 교체점은 어댑터로만. 도메인/오케스트레이터는 구체 구현 직접 import 금지 — `ports.py` 경유.
6. `ports.py` 동결 전 stage 구현 금지.
7. 새 외부 모델/엔진 = 기존 코드 수정이 아니라 **새 어댑터 파일 추가**.

**프로세스·품질**
8. TDD: 구현 전 실패 테스트 먼저. 도메인·정렬·믹싱은 단위테스트 필수.
9. 머지 전 리뷰 게이트 필수. 통과 없이 "완료" 선언 금지.
10. 검증 없는 완료 주장 금지 — 테스트/실행 출력으로 증명.
11. 버그·예외는 추측 수정 금지 → systematic-debugging.
12. 조용한 실패 금지: 단계 실패는 잡 상태 `failed`(단계+원인)로 표면화.

**데이터·안전**
13. 업로드 악보·생성 음원·교정 데이터는 사용자 자산. `data/`·모델·대용량 WAV 커밋 금지.
14. 외부 입력 경로 변경 시 `security-reviewer` 필수(traversal·파일타입·크기).
15. L4 라벨은 원본과 분리, 개인식별자 미포함.
16. 외부 전송/공개(배포·업로드)는 명시 승인 전 금지.

**단계·범위**
17. 1단계 스코프 고정: 음표→"우"→믹싱. 가사 관련은 `[2단계]` 유지(YAGNI).
18. 수직 슬라이스 우선.
19. `training/`(트랙 B)는 서빙 요청 경로에 들이지 않음.
20. 응답·문서·주석은 한국어 기본.

## 7. 잡 상태 모델
```
queued → omr → parsing → [lyric → align] → synth → mixing → done
                                                          ↘ failed
```
`[lyric → align]` 구간은 2단계에만 활성.
