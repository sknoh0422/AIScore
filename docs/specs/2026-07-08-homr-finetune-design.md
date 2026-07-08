# homr 파인튜닝 실현성 설계 (Stage E 착수)

> **목표:** 답지(GT)가 있는 새찬송가 645곡에서 homr 인식 정확도를 **현재 성부 F1 80% → 목표 ~99%**로 끌어올릴 수 있는지 **실측으로 검증**한다. 되면 homr을 우리 OMR 엔진으로 확정, 안 되면 대안 베이스(SMT 등)로.
> 상위 맥락: [ROADMAP](../ROADMAP.md) Stage E, 메모리 `omr-strategy-own-engine`.

**작성:** 2026-07-08 · **상태:** 설계(리뷰 대기)

---

## 1. 배경·전제 (검증 완료)

- **"리듬이 최대 병목"은 측정 아티팩트.** 전곡 642 SER 분해(선행/후행 쉼표 제거): 피치순서 0.263 > 순수 리듬 0.155. SER(pd)가 피치 오류를 이중 계상했던 것. → 진짜 지렛대는 피치/조표(파인튜닝).
- **homr 오류 지배 패턴 = 조표 플랫 과소인식**(44곡, Ab→Eb 등). 체계적 오류 → 파인튜닝이 잘 고치는 유형.
- **homr `--fine` = encoder/decoder 동결 + lift(임시표 #/♭/♮) 디코더만 학습.** 우리 #1 오류를 정조준. (실증: `pytorch_model_396`에 `decoder.net.*lift*` 파라미터 존재.)
- **파인튜닝 베이스 확보:** `pytorch_model_396`(278MB, 우리 추론 ONNX와 동일 run) 다운로드+torch-CPU 로드 검증 완료. 위치: `homr/training/architecture/transformer/`.
- **하드웨어:** 학습=4090 Windows PC(WSL2+CUDA, 비용 0). Mac=데이터생성·평가·서빙. 클라우드 배제(운영비 0 제약).

## 2. 설계 결정 (권고안 — 리뷰 확정 대상)

| # | 결정 | 권고 | 근거 |
|---|------|------|------|
| ① | 학습 이미지 렌더 | **MuseScore로 645 GT 렌더** (homr `convert_lieder` 파이프라인 준용) | 학습쌍은 (staff 이미지↔토큰) 정렬이 필요 → 심볼 소스에서 직접 렌더해야 정렬됨. MuseScore는 homr 지원 렌더러(in-distribution). 실제 사진 일반화는 실스캔 확보 후 후속 실험. |
| ② | 성공 지표 | **주=SATB 성부별 F1**(현 80% 베이스와 직접 비교), 보조=homr staff-token NED | "80%→99%"는 우리 F1 기준. NED는 homr 자체 벤치 비교용. |
| ③ | 파인튜닝 범위 | **1차 `--fine`(임시표만)**, 정체 시 전체 파인튜닝으로 단계 확대 | 최소 비용·최대 표적(조표). 4090서 수시간. 피치/리듬/성부 못 고치면 unfreeze 확대. |

**측정 설계:** 645를 train/held-out 분할. 1차 게이트=held-out MuseScore 렌더 F1(전/후). 전이 확인=기존 `eval_satb.py`를 NWC 렌더(homr_full)에 재실행(MuseScore 학습이 다른 렌더로 전이되나).

## 3. 작업 분담

### Mac에서 완료 (GPU 불필요) — 이식 전
1. ✅ 베이스 `.pth` 다운로드+검증 완료.
2. **데이터 생성기** `training/scripts/convert_saechan.py` — 645 GT MusicXML → MuseScore SVG 렌더 → staff 이미지 크롭 + homr 토큰(rhythm/pitch/lift/note) 라벨 + `index.txt`. (`homr/training/omr_datasets/convert_lieder.py`·`music_xml_parser.py` 재사용.)
   - 의존: MuseScore(mac 앱), `rsvg-convert`(brew), homr 토크나이저.
   - 산출: `train.index` / `heldout.index` (곡 단위 분할, 누수 방지).
3. **학습 번들** 패키징 — 데이터 + 베이스 `.pth` + config + 런북. 크기 수백MB.
4. **평가 하니스** — `eval_satb.py` 재사용 + held-out MuseScore 채점 경로 추가.

### 4090 WSL2에서만 (GPU 필요)
5. 환경: WSL2 Ubuntu + CUDA(`nvidia-smi` 확인) + `poetry install --only main,gpu` + apt(librsvg2-bin, libfuse2, libjack) + MuseScore.
6. `train.py transformer --fine` (베이스=pytorch_model_396) → `pytorch_model_<run>.pth`.
7. 결과 → ONNX export → Mac 복사 → `HomrAdapter` 가중치 스위치 → `eval_satb.py` 전/후 비교.

## 4. Windows(WSL2) 실행 절차 — Claude Code 내에서

> 4090 PC의 WSL2 Ubuntu에 **Claude Code 설치** → AIScore 레포 clone(이 스펙·ROADMAP·메모리 맥락 승계) → 아래를 에이전트가 실행.

```
0. 사전: Windows11 최신 NVIDIA 드라이버 + WSL2 Ubuntu.  WSL 내 `nvidia-smi`로 4090 확인.
1. git clone homr + AIScore.  homr: poetry install --only main,gpu.
2. 학습 번들(Mac 산출) 배치: train.index/heldout.index + 이미지 + pytorch_model_396.pth.
3. python training/train.py transformer --fine   # lift 디코더 학습, 4090서 수시간
4. 산출 .pth → ONNX export.
5. ONNX → Mac 전송(또는 WSL 내 eval).  eval_satb.py로 held-out 전/후 F1 비교.
6. 판정: 목표 근접 → homr 확정 / 정체 → 전체 파인튜닝(범위③ 확대) 또는 Q2(대안 베이스).
```

## 5. 성공/실패 기준

- **성공(게이트 통과):** held-out F1이 목표에 유의하게 접근(특히 조표 플랫 곡 F1 개선). → homr 엔진 확정, 전체 파인튜닝·실스캔 일반화로 진행.
- **부분:** 조표는 개선되나 피치/성부 정체 → 범위③ 전체 파인튜닝으로 확대 재실험.
- **실패:** `--fine`+전체 파인튜닝 모두 645조차 목표 미달 → homr 모델 클래스 한계 → Q2(SMT/SMT++ 등 대안 베이스 웹조사·트라이얼).

## 6. 범위 밖 (YAGNI)

- 실제 새찬송가 스캔 데이터 확보/증강 — 게이트 통과 후 별도 설계.
- L4 교정 에디터 플라이휠 — 별도.
- 2단계 가사 — 무관.
