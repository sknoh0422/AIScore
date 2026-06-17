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
- **oemer 통합 스모크(수동)** — 실제 악보 인식 품질 미검증(설계 §2 "가장 약한 고리").
  실행: `cd backend && PATH=/opt/miniconda3/envs/aiscore/bin:$PATH PYTHONPATH=. /opt/miniconda3/envs/aiscore/bin/python -m pytest -v -m integration`
- **GitHub push** — `main`을 origin에 푸시(데스크탑 앱 또는 인증된 터미널).

## 📋 예정 (다음 후보, 각각 별도 spec→plan)
- **프론트엔드** — Next.js + OSMD: 업로드·잡 상태·악보 렌더·교정 에디터.
- **2단계 가사** — 가사 소스(텍스트 입력 기본/OCR 보조) + 음절↔음표 정렬(slur/tie/절) + 가사 가창 SVS 어댑터.
- **L4 교정 로깅** — 교정 결과를 (이미지영역, 오답, 정답) 라벨로 누적(플라이휠).
- **트랙 B(오프라인)** — 누적 라벨로 한글 OCR 지도학습(`training/`).
- **품질 개선(1단계 리뷰 후속, IMPORTANT)** — 파트<4 방어(파서), 업로드 크기 제한, 믹서 스테레오 mix-down, 테스트 store 격리, `test_ports.py` 포트 계약 테스트 채우기.

---

## 단계 정의 (요약)
```
1단계: 음표 → 모음 "우" → 믹싱            ← 완료
2단계: + 가사(텍스트/OCR) + 정렬 + 가사가창  ← 예정
트랙B: 교정데이터 → 한글 OCR 지도학습(오프라인)
```
