# AIScore

4성부 찬송가 악보(SATB) 이미지를 업로드하면 각 성부를 AI 목소리로 노래시켜
**AI 찬양대 합창 음원**을 생성하는 웹 서비스.

```
악보 이미지 → OMR → music21 파싱(SATB 분리) → SVS(성부별 가창) → 믹싱 → 합창 WAV
```

## 단계
- **1단계** (현재): 가사 없이 모음 "우"로 합창 → 연습 가이드 트랙.
- **2단계**: 가사(텍스트 입력/OCR) + 음절 정렬 + 가사 가창.
- **트랙 B**: 교정 데이터로 한글 OCR 지도학습 (오프라인).

## 구조
```
backend/    FastAPI 서버 (헥사고날: api → orchestration → domain, stages 어댑터)
frontend/   Next.js + OSMD (악보 렌더 + 교정 에디터)
training/   오프라인 모델 R&D (트랙 B)
docs/       설계 문서
score_images/  샘플 악보
```

## 개발 규약
- 프로젝트 헌법: [CLAUDE.md](CLAUDE.md)
- 설계 문서: [docs/superpowers/specs/2026-06-16-aiscore-design.md](docs/superpowers/specs/2026-06-16-aiscore-design.md)
- 환경: conda `aiscore` (Python 3.10) — `conda env create -f aiscore_env.yml`
- 개발: macOS(Apple Silicon, MPS), 다중 OS 이식성 목표.

## 상태
설계 확정 + 스캐폴딩 단계. 구현 미시작.
