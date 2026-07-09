# homr 파인튜닝 실현성 설계 (Stage E 착수)

> **목표:** 답지(GT)가 있는 새찬송가 645곡에서 homr 인식 정확도를 **현재 성부 F1 80% → 목표 ~99%**로 끌어올릴 수 있는지 **실측으로 검증**한다. 되면 homr을 우리 OMR 엔진으로 확정, 안 되면 대안 베이스(SMT 등)로.
> 상위 맥락: [ROADMAP](../ROADMAP.md) Stage E, 메모리 `omr-strategy-own-engine`.

**작성:** 2026-07-08 · **상태:** ✅ **확정**(2026-07-09 `../homr` 코드검증 리뷰 — 결정 ①②③ 확정, ③ 근거 정정 + 무비용 사전 게이트 추가)

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

**측정 설계:** 645를 train/held-out 분할. 1차 게이트=held-out MuseScore 렌더 F1(전/후). **진짜 게이트=NWC 렌더 전이 F1**(아래 리뷰 확정 참조).

---

## 2.1 리뷰 확정 (2026-07-09, `../homr` 코드 대조)

**결정 3개 모두 확정.** 단 ①은 게이트 위상 조정, ③은 근거 정정 + 사전 게이트 추가.

**① MuseScore 렌더 — 확정(조건부).** homr 학습 파이프라인(`convert_lieder.py`+`musescore_svg.py`, MuseScore 4.6.5)이 이 렌더러 전용이라 토큰-정렬 학습쌍 생성의 유일한 실현 경로. **단 리스크 명문화:** 확정 결론은 "12%p 손실 = homr의 **새찬송가 조판** 인식 한계"였는데, MuseScore 조판으로 파인튜닝하면 이미 잘 인식하는 분포를 학습할 뿐 새찬송가 갭이 안 닫힐 수 있음. → **held-out MuseScore F1은 약한 프록시. 성공 판정의 진짜 기준은 NWC 렌더(`homr_full`) 전이 F1.** MuseScore 렌더로 개선됐으나 NWC 전이가 없으면 = 실패로 간주하고 **NWC-네이티브 학습**(기존 800px PNG + homr 보표검출 크롭 + GT 토큰)을 Q2(SMT) 이전 폴백으로 사전 등록.

**② SATB 성부별 F1 — 확정(무수정).** 현 80% 베이스 직접 비교 가능, 제품 목표와 일치. 보조 NED 유지.

**③ 1차 `--fine` — 확정(근거 정정).** 코드 검증 결과 스펙 원문의 "조표 정조준"은 부정확:
  - 조표 `keySignature_{-7..7}`=**rhythm 헤드**(`--fine`서 동결) / lift(음표별 #/♭/♮)=**lift 헤드**(`--fine`서 학습). 서로 다른 헤드.
  - **그러나 ③은 유효.** 최종 발음 피치=`pitch헤드+lift헤드`(`music_xml_generator.py:626-629`, 조표 토큰은 발음 피치 미변경). 학습 라벨 lift는 조표 유래 alter 포함(`_lift_from_pitch_or_accidental`). 우리 F1=발음 피치이므로 플랫 과소인식의 피치 영향은 **lift 헤드 경유** → `--fine`이 학습하는 헤드가 맞음.
  - **정정된 한계:** `--fine`은 **표기상 조표 토큰은 못 고침**(rhythm 헤드 동결). 우리 F1(발음 피치)엔 무관하나, 표기 조표가 필요한 소비자에겐 별도.

**★ 신규 무비용 사전 게이트 (GPU 착수 전, Mac, Task 2.5로 삽입):**
"반음 하향 전조"가 lift 헤드가 아니라 **pitch 헤드(보표 위치 오독)** 에서 나오면 `--fine`으론 못 고치고 GPU 시간 낭비. → **44곡 플랫 오류에 대해 homr 실행 후 per-note 토큰(rhythm/pitch/lift)을 GT 토큰과 대조해 오류가 어느 헤드에 몰리는지 귀속 분석**:
  - lift 헤드 지배 → `--fine` 1차 진행(계획대로).
  - pitch/keySignature(rhythm) 헤드 지배 → `--fine` 건너뛰고 **바로 전체(또는 decoder) 파인튜닝**(범위③ 확대).

### 2.2 게이트 실행 결과 (2026-07-09, `head_attribution.py` 전곡 642)

측정: 발음 피치를 `staff bag{step,octave}`(=pitch 헤드)와 `sound bag{step,octave,alter}`(=pitch+lift)로 분해, 멀티셋 F1 비교.

| 슬라이스 | n | staff_F1 (pitch헤드) | sound_F1 (pitch+lift) | lift_gap |
|----------|---|---------------------|----------------------|----------|
| 전곡 | 642 | 0.903 | 0.880 | 0.023 |
| **플랫 과소인식**(homr fifths > gt) | 46 | **0.903** | **0.809** | **0.094** |
| 저 발음F1 하위25% | 160 | 0.794 | 0.742 | 0.053 |

예: hymn373 GT −3플랫→homr −1플랫, staff_F1 0.843(정상)인데 sound_F1 0.393(붕괴). hymn446 staff 0.980→sound 0.788.

**게이트 판정 — `--fine` 진행 확정, 단 상한 명시:**
1. ✅ **플랫 과소인식 = lift 헤드 지배 확정.** 그 46곡에서 pitch 헤드는 전혀 안 깎이고(0.903, 전곡과 동일) 발음 F1만 0.809로 내려감 → 9.4pp 격차 전부 lift 헤드. `--fine`이 학습하는 바로 그 헤드 → **정조준 맞음.**
2. ⚠️ **`--fine` 단독 이론 상한 = pitch 헤드 F1 = 0.903.** 목표 0.99는 **수학적으로 `--fine`만으론 불가.** 저F1 하위 집단은 pitch 헤드가 깎임(0.903→0.794) → 여기는 **전체 파인튜닝(pitch 헤드 unfreeze)만** 회복 가능.
3. **결론:** `--fine`은 실제 체계적 오류(46곡, 검증 조로 약 +9pp) 회복에 유효하고 값싸 **1차로 진행**. 그러나 글로벌 F1은 0.903 상한에 막히므로 **"정체 시 전체 파인튜닝 확대"(범위③)는 거의 확실히 발동** → GPU 예산에 전체 파인튜닝 사이클을 미리 반영.

산출물: `training/baseline_eval/head_attribution.json`, 스크립트 `training/scripts/head_attribution.py`.

## 3. 작업 분담

### 환경 사실 (2026-07-09 실측)
- **MuseScore 4.7.3 mac: `-j` job 모드만 작동, `-o` 단일 변환은 exit 40 실패.** convert_lieder가 쓰는 게 `-j`라 Mac 데이터 생성 가능. (offscreen Qt 플러그인 없음 → cocoa만. GUI 세션 필요.) 산출 파일명은 페이지별 `<name>-1.svg`.
- `rsvg-convert` 2.62.3 설치 완료(brew librsvg).
- homr `music_xml_parser` = homr venv 필요(cv2/musicxml 존재) + **torch-CPU 추가 설치**(training_vocabulary 의존).

### Mac에서 완료 (GPU 불필요) — 이식 전
1. ✅ 베이스 `.pth` 다운로드+검증 완료.
2. **데이터 생성기** `training/scripts/convert_saechan.py` — 645 GT MusicXML → MuseScore SVG 렌더 → staff 이미지 크롭 + homr 토큰(rhythm/pitch/lift/note) 라벨 + `index.txt`. (`homr/training/omr_datasets/convert_lieder.py`·`music_xml_parser.py` 재사용.)
   - 의존: MuseScore(mac 앱), `rsvg-convert`(brew), homr 토크나이저.
   - 산출: `train.index` / `heldout.index` (곡 단위 분할, 누수 방지).
2.5. **★ 헤드 귀속 사전 게이트**(GPU 착수 전 필수) — 44곡 플랫 오류에 homr 실행 → per-note 토큰(rhythm/pitch/lift) vs GT 대조 → 오류 헤드 분포 산출. lift 지배면 `--fine` 진행 / pitch·rhythm 지배면 전체 파인튜닝으로 직행. (§2.1 신규 게이트.)
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
