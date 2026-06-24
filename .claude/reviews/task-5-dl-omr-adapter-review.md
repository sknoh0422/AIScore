# Task 5 코드 리뷰: 백엔드 DL-OMR 어댑터

**리뷰 날짜:** 2026-06-23  
**커밋 범위:** ea0b33f..dbe4af5  
**결정:** REQUEST CHANGES (1 HIGH, 2 MEDIUM, 1 LOW)

---

## 스펙 체크리스트

| 항목 | 결과 | 비고 |
|------|------|------|
| `dl_omr_adapter.py` 위치 (`backend/app/stages/omr/`) | ✅ | 정확한 위치에 생성 |
| `DlOmrAdapter` implements `OmrPort` | ✅ | `isinstance(adapter, OmrPort)` 통과 |
| `training/` import 없음 | ✅ | 인라인 복사 방식, 의존 없음 |
| `IMG_W, IMG_H = 2048, 128` | ✅ | train_omr.py 와 동일 |
| `backbone.maxpool = nn.Identity()` | ✅ | stride 16 확보 |
| vocab size = 119 | ✅ | 테스트로도 검증됨 |
| `model_path=None` → 생성자 에러 없음 | ✅ | |
| `model_path=None` → `recognize()` RuntimeError | ✅ | match="모델 가중치" |
| 2개 필수 테스트 존재 및 통과 | ✅ | 7/7 통과 (2 필수 + 5 추가) |
| `domain/` 파일 수정 없음 | ✅ | |

---

## 발견 사항

### HIGH

#### H1. `torch.load()` weights_only 파라미터 누락 — 임의 코드 실행 위험
**파일:** `backend/app/stages/omr/dl_omr_adapter.py`, 라인 154  
**코드:**
```python
ckpt = torch.load(model_path, map_location="cpu")
```
**문제:** PyTorch 2.0+ 에서 `torch.load()` 는 기본적으로 pickle 역직렬화를 수행하며, 신뢰할 수 없는 `.pt` 파일 로드 시 임의 코드 실행(RCE)이 가능하다. `weights_only=True` 를 지정하지 않으면 모델 경로가 외부 입력으로 전달될 경우 보안 취약점이 된다.  
**수정:**
```python
ckpt = torch.load(model_path, map_location="cpu", weights_only=True)
```
단, 체크포인트에 `vocab_tok2idx` 등 custom Python 객체가 포함된 경우 `weights_only=False` 를 유지하되, 운영 환경에서는 경로 검증과 파일 무결성 확인(해시)을 별도 적용해야 한다.  
> CLAUDE.md 규칙 14: 외부 입력 경로 변경 시 security-reviewer 필수. 모델 경로는 외부 설정값이므로 해당.

---

### MEDIUM

#### M1. 브리프 지정 테스트 경로와 실제 경로 불일치
**브리프 지정:** `tests/stages/omr/test_dl_omr_adapter.py` (repo root 기준 top-level)  
**실제 생성:** `backend/tests/test_dl_omr_adapter.py`  
**영향:** 브리프에서 지정한 디렉터리 구조와 다르다. 현재 프로젝트의 다른 테스트들도 `backend/tests/` 에 있으므로 실질적인 버그는 아니나, 브리프 추적성이 깨진다. 브리프를 따르거나, 보고서에 경로 변경 이유를 명시해야 한다.

#### M2. `_OmrCRNN.__new__` 패턴 — `isinstance` 체크 오류 위험
**파일:** `backend/app/stages/omr/dl_omr_adapter.py`, 라인 84-104  
**코드:**
```python
class _OmrCRNN:
    def __new__(cls, vocab_size: int):
        class _Inner(nn.Module): ...
        return _Inner(vocab_size)
```
**문제:** `_OmrCRNN(vocab_size)` 는 실제로 `_Inner` 인스턴스를 반환하므로, `isinstance(self._model, _OmrCRNN)` 는 항상 `False` 가 된다. 현재 코드에서는 해당 isinstance 체크가 없어 버그로 발현되지 않지만, 향후 `self._model.eval()` / `self._model.load_state_dict()` 호출이 `_Inner`(nn.Module) 에 위임되므로 우발적 추가 시 혼란을 유발한다.  
**권장:** 지연 import 가 필요하다면 `_OmrCRNN` 자체를 `nn.Module` 서브클래스로 유지하되 팩토리 함수(`_make_crnn(vocab_size) -> nn.Module`)로 분리하는 것이 더 명확하다.

---

### LOW

#### L1. `_notes_to_musicxml`의 `time_sig` 파라미터 사용되지 않음
**파일:** `backend/app/stages/omr/dl_omr_adapter.py`, 라인 109-134  
**문제:** `time_sig: str = "4/4"` 를 받지만 함수 내에서 `m21` 스트림에 TimeSignature 를 추가하는 코드가 없다. 결과 MusicXML 에 박자표가 없어서 OSMD 렌더링 시 기본값으로 처리된다. 파라미터를 사용하거나 제거해야 한다.

---

## 아키텍처 정확도 검증 (train_omr.py 비교)

| 항목 | train_omr.py | dl_omr_adapter.py | 일치 |
|------|-------------|-------------------|------|
| `IMG_W, IMG_H` | `2048, 128` | `2048, 128` | ✅ |
| `backbone.maxpool` | `nn.Identity()` | `nn.Identity()` | ✅ |
| `encoder` | `children()[:-2]` | `children()[:-2]` | ✅ |
| `pool_h` | `AdaptiveAvgPool2d((1, None))` | `AdaptiveAvgPool2d((1, None))` | ✅ |
| LSTM hidden | 256, 2층, bidirectional | 256, 2층, bidirectional | ✅ |
| heads | 4성부 `Linear(512, vocab_size)` | 4성부 `Linear(512, vocab_size)` | ✅ |
| specials | `["<BLK>","<EOS>","TIE_S","TIE_E"]` | 동일 | ✅ |
| vocab size | 119 | 119 (테스트 검증) | ✅ |
| blank_idx | 0 | 0 (테스트 검증) | ✅ |
| `decode()` 로직 | CTC 중복 제거 없음 (단순 순회) | 동일 | ✅ |
| **주의**: train_omr.py는 `weights=DEFAULT` | 프리트레인 사용 | adapter는 `weights=None` | ⚠️ 의도적 차이 (추론용) |

> `weights=None` 은 추론 시 올바른 선택 — 체크포인트에서 fine-tuned 가중치를 로드하므로 pretrained init 불필요.

---

## 검증 결과

| 항목 | 결과 |
|------|------|
| `test_dl_omr_adapter_implements_omr_port` | PASS |
| `test_dl_omr_adapter_no_model_raises` | PASS |
| 추가 5개 테스트 | PASS |
| 전체 백엔드 테스트 (98개) | PASS, 0 failed |
| `training/` 직접 import 없음 | PASS |
| `domain/` 수정 없음 | PASS |

---

## 결론

스펙 요구사항은 모두 충족되며 테스트도 통과한다. 단, **H1 (torch.load weights_only)** 는 외부 모델 파일을 로드하는 경로에 대한 보안 취약점으로, CLAUDE.md 규칙 14 적용 대상이다. 운영 배포 전 수정 필요.

**H1을 수정한 후 재승인** 필요. M1, M2는 권장 수정이며 블로커는 아님.
