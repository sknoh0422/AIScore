# Plan 1B — OMR 모델 학습 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 644쌍 찬송가 이미지↔MusicXML로 CRNN 기반 OMR 모델을 학습하고 `OmrPort` 어댑터로 연결하여 이미지 → OSMD 렌더링 파이프라인을 완성한다.

**Architecture:** 이미지 인코더(ResNet18 pretrained) + 4성부 독립 CTC 헤드로 각 성부의 음표 토큰 시퀀스를 예측한다. 학습은 `training/` 트랙에서만 수행하며, `backend/`에는 추론 어댑터(`DlOmrAdapter`)만 추가한다.

**Tech Stack:** Python 3.10 / torch 2.10 / torchvision 0.25 / music21 / Pillow / scikit-learn / pytest

## Global Constraints

- Python: `/opt/miniconda3/envs/aiscore/bin/python` (conda `aiscore`, py3.10)
- 디바이스: `core/device.py` 패턴 — MPS→CUDA→CPU 자동 선택
- 학습 데이터·모델 가중치: `data/`·`models/` 디렉터리는 `.gitignore` 처리, 커밋 금지
- `domain/` 파일 수정 금지 (ports.py 동결)
- `backend/`에서 torch import: `stages/omr/dl_omr_adapter.py` 한 파일에만 허용
- 응답·주석·변수명: 한국어 주석 허용, 코드 식별자는 영문
- 테스트 실행 시 `integration` 마크는 기본 제외: `pytest -m "not integration"`
- 각 태스크 완료 후 커밋 필수

---

## 파일 구조

```
training/
├── data/                          # gitignore — 생성 데이터
│   ├── labels/                    # hymn001.json ~ hymn645.json (XML→JSON 변환본)
│   └── splits.json                # train/val/test 분할 인덱스
├── models/                        # gitignore — 학습 가중치
│   └── omr_crnn_best.pt
├── notebooks/
│   ├── 01_data_prep.ipynb         # Task 1 스크립트 시각화 래퍼
│   └── 02_train_omr.ipynb         # Task 3 학습 루프 시각화 래퍼
└── scripts/
    ├── convert_nwc_to_xml.py      # 기존
    ├── download_nwc.py            # 기존
    ├── data_prep.py               # Task 1: XML→JSON + 데이터셋 분할
    └── train_omr.py               # Task 3: CRNN 모델 정의 + 학습 루프

backend/app/stages/omr/
└── dl_omr_adapter.py              # Task 5: 학습 가중치 로드, OmrPort 구현

tests/
└── training/
    ├── test_data_prep.py          # Task 1 단위 테스트
    ├── test_vocab.py              # Task 3 어휘 테스트
    └── test_dl_omr_adapter.py    # Task 5 어댑터 테스트
```

---

## Task 1: 데이터 준비 — XML→JSON 라벨 추출 + 분할

**Files:**
- Create: `training/scripts/data_prep.py`
- Create: `tests/training/test_data_prep.py`
- Create: `training/data/.gitkeep` (디렉터리 추적용)
- Create: `training/models/.gitkeep`

**Interfaces:**
- Produces:
  - `parse_xml(xml_path: Path) -> dict` — 한 XML → 라벨 dict 반환
  - `build_dataset(png_dir, xml_dir, out_dir) -> list[dict]` — 전체 644쌍 처리
  - `split_dataset(items, seed=42) -> dict` — train/val/test 분할 반환

**라벨 JSON 구조:**
```json
{
  "hymn_id": "001",
  "image_path": "score_images/png/hymn001_Normal.png",
  "time_signature": "4/4",
  "key_signature": -4,
  "measures": [
    {
      "measure_num": 1,
      "S": [{"pitch": "A-4", "duration": 1.0, "tie_start": false, "tie_end": false}],
      "A": [{"pitch": "E-4", "duration": 1.0, "tie_start": false, "tie_end": false}],
      "T": [{"pitch": "C4",  "duration": 1.0, "tie_start": false, "tie_end": false}],
      "B": [{"pitch": "A-3", "duration": 1.0, "tie_start": false, "tie_end": false}]
    }
  ]
}
```

- [ ] **Step 1: 테스트 파일 생성 및 실패 확인**

```python
# tests/training/test_data_prep.py
import pytest
from pathlib import Path

PNG_DIR = Path("score_images/png")
XML_DIR = Path("score_images/xml/분리")
SAMPLE_XML = XML_DIR / "새찬송가_001 만복의근원하나님.xml"


def test_parse_xml_returns_required_keys():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    assert "hymn_id" in result
    assert "measures" in result
    assert len(result["measures"]) > 0


def test_parse_xml_measure_has_four_voices():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    m = result["measures"][0]
    for voice in ("S", "A", "T", "B"):
        assert voice in m, f"voice {voice} missing"


def test_parse_xml_note_has_required_fields():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    # measure 0은 전주(쉼표)일 수 있으니 첫 음표가 있는 마디 탐색
    note = None
    for m in result["measures"]:
        for v in ("S", "A", "T", "B"):
            if m[v]:
                note = m[v][0]
                break
        if note:
            break
    assert note is not None
    for field in ("pitch", "duration", "tie_start", "tie_end"):
        assert field in note, f"field {field} missing"


def test_split_dataset_ratios():
    from training.scripts.data_prep import split_dataset
    items = [{"hymn_id": str(i)} for i in range(100)]
    splits = split_dataset(items, seed=42)
    assert "train" in splits and "val" in splits and "test" in splits
    total = len(splits["train"]) + len(splits["val"]) + len(splits["test"])
    assert total == 100
    assert 75 <= len(splits["train"]) <= 82  # ~80%
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore
/opt/miniconda3/envs/aiscore/bin/python -m pytest tests/training/test_data_prep.py -v
```
Expected: `ImportError` 또는 `ModuleNotFoundError` (파일 없음)

- [ ] **Step 3: `training/scripts/data_prep.py` 구현**

```python
"""XML→JSON 라벨 추출 + train/val/test 분할."""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

import music21 as m21
from sklearn.model_selection import train_test_split

log = logging.getLogger(__name__)

PNG_DIR = Path("score_images/png")
XML_DIR = Path("score_images/xml/분리")
OUT_DIR = Path("training/data")

VOICE_ORDER = ("S", "A", "T", "B")  # Part 0~3 순서


def _hymn_num_from_xml(xml_path: Path) -> str:
    """새찬송가_001 ... → '001'"""
    m = re.match(r"새찬송가_(\d+)", xml_path.stem)
    if not m:
        raise ValueError(f"XML 파일명 패턴 불일치: {xml_path.name}")
    return m.group(1)


def _note_to_dict(n: m21.note.GeneralNote) -> dict:
    if isinstance(n, m21.note.Rest):
        return {
            "pitch": "REST",
            "duration": float(n.duration.quarterLength),
            "tie_start": False,
            "tie_end": False,
        }
    pitch_str = n.pitch.nameWithOctave  # e.g., "A-4"
    tie_start = n.tie is not None and n.tie.type in ("start", "continue")
    tie_end = n.tie is not None and n.tie.type in ("stop", "continue")
    return {
        "pitch": pitch_str,
        "duration": float(n.duration.quarterLength),
        "tie_start": tie_start,
        "tie_end": tie_end,
    }


def parse_xml(xml_path: Path) -> dict:
    """MusicXML → 라벨 dict. measures 리스트는 measure_num 기준 정렬."""
    hymn_id = _hymn_num_from_xml(xml_path)
    png_name = f"hymn{hymn_id}_Normal.png"

    score = m21.converter.parse(str(xml_path))
    parts = score.parts
    if len(parts) < 4:
        raise ValueError(f"{xml_path.name}: 파트 수 {len(parts)} < 4")

    # 박자표 / 조표
    ts = score.flatten().getElementsByClass("TimeSignature")
    ks = score.flatten().getElementsByClass("KeySignature")
    time_sig = str(list(ts)[0]) if ts else "4/4"
    key_sig = list(ks)[0].sharps if ks else 0

    # 성부별 마디 → 음표 추출
    measures_by_num: dict[int, dict] = {}
    for voice_idx, voice_name in enumerate(VOICE_ORDER):
        part = parts[voice_idx]
        for measure in part.getElementsByClass("Measure"):
            mnum = measure.number
            if mnum not in measures_by_num:
                measures_by_num[mnum] = {"measure_num": mnum, "S": [], "A": [], "T": [], "B": []}
            notes = [_note_to_dict(n) for n in measure.flatten().notesAndRests]
            measures_by_num[mnum][voice_name] = notes

    measures = sorted(measures_by_num.values(), key=lambda x: x["measure_num"])
    # measure_num=0 (전주 쉼표 마디) 제거
    measures = [m for m in measures if m["measure_num"] > 0]

    return {
        "hymn_id": hymn_id,
        "image_path": str(PNG_DIR / png_name),
        "time_signature": time_sig,
        "key_signature": key_sig,
        "measures": measures,
    }


def split_dataset(items: list[dict], seed: int = 42) -> dict[str, list[dict]]:
    """80/10/10 train/val/test 분할."""
    train_val, test = train_test_split(items, test_size=0.1, random_state=seed)
    train, val = train_test_split(train_val, test_size=0.111, random_state=seed)
    return {"train": train, "val": val, "test": test}


def build_dataset(
    png_dir: Path = PNG_DIR,
    xml_dir: Path = XML_DIR,
    out_dir: Path = OUT_DIR,
) -> list[dict]:
    """전체 XML 처리 → JSON 저장 → splits.json 저장."""
    out_dir.mkdir(parents=True, exist_ok=True)
    labels_dir = out_dir / "labels"
    labels_dir.mkdir(exist_ok=True)

    items = []
    failed = []
    xml_files = sorted(xml_dir.glob("새찬송가_*.xml"))
    for xml_path in xml_files:
        try:
            label = parse_xml(xml_path)
        except Exception as e:
            log.warning("SKIP %s: %s", xml_path.name, e)
            failed.append(xml_path.name)
            continue
        # 이미지 존재 확인
        img = Path(label["image_path"])
        if not img.exists():
            log.warning("이미지 없음: %s", img)
            failed.append(xml_path.name)
            continue
        label_path = labels_dir / f"hymn{label['hymn_id']}.json"
        label_path.write_text(json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8")
        items.append({"hymn_id": label["hymn_id"], "label_path": str(label_path)})

    splits = split_dataset(items)
    splits_path = out_dir / "splits.json"
    splits_path.write_text(json.dumps(splits, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("완료: %d 성공, %d 실패", len(items), len(failed))
    if failed:
        log.warning("실패 목록: %s", failed)
    return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build_dataset()
```

- [ ] **Step 4: `training/` 패키지 구조 확인 및 `__init__.py` 생성**

```bash
ls training/scripts/__init__.py 2>/dev/null || touch training/__init__.py training/scripts/__init__.py
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore
/opt/miniconda3/envs/aiscore/bin/python -m pytest tests/training/test_data_prep.py -v
```
Expected: 4 passed

- [ ] **Step 6: 전체 데이터셋 빌드 실행**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore
/opt/miniconda3/envs/aiscore/bin/python training/scripts/data_prep.py
```
Expected: `완료: 644 성공, 0 실패` (또는 실패 파일은 WARNING 출력)
확인: `ls training/data/labels/ | wc -l` → 644

- [ ] **Step 7: .gitignore 업데이트 및 커밋**

```bash
# .gitignore에 추가 확인
grep -q "training/data" .gitignore || echo "training/data/" >> .gitignore
grep -q "training/models" .gitignore || echo "training/models/" >> .gitignore

git add training/scripts/data_prep.py tests/training/test_data_prep.py \
        training/__init__.py training/scripts/__init__.py \
        training/data/.gitkeep training/models/.gitkeep .gitignore
git commit -m "feat(training): XML→JSON 라벨 추출 + train/val/test 분할 (644쌍)"
```

---

## Task 2: 기준선 평가 — Audiveris vs Ground Truth

**Goal:** Audiveris 소프라노 음표 정확도를 val set 20개로 측정하여 <95% 확인 후 자체 학습 정당화.

**Files:**
- Create: `training/scripts/baseline_eval.py`

**Interfaces:**
- Consumes: `training/data/splits.json`, `training/data/labels/`
- Produces: stdout 정확도 보고서

- [ ] **Step 1: 기준선 평가 스크립트 작성**

```python
# training/scripts/baseline_eval.py
"""Audiveris 기준선 정확도 측정 — val set 20개."""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

import music21 as m21

log = logging.getLogger(__name__)

SPLITS = Path("training/data/splits.json")
LABELS = Path("training/data/labels")
AUDIVERIS = Path("vendor/audiveris/bin/Audiveris")
JDK25 = "/opt/homebrew/opt/openjdk@25/bin/java"
SAMPLE_SIZE = 20


def run_audiveris(image_path: Path, out_dir: Path) -> Path | None:
    if not AUDIVERIS.exists():
        log.warning("Audiveris 없음: %s", AUDIVERIS)
        return None
    cmd = [
        JDK25, "-jar", str(AUDIVERIS),
        "-batch", "-transcribe", "-export",
        "-output", str(out_dir), str(image_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    mxl = next(out_dir.glob("**/*.mxl"), None)
    return mxl


def pitch_accuracy(pred_notes: list[str], gt_notes: list[str]) -> float:
    if not gt_notes:
        return 1.0
    correct = sum(p == g for p, g in zip(pred_notes, gt_notes))
    return correct / max(len(pred_notes), len(gt_notes))


def extract_soprano_pitches(mxl_path: Path) -> list[str]:
    try:
        score = m21.converter.parse(str(mxl_path))
        if not score.parts:
            return []
        part = score.parts[0]
        return [
            n.pitch.nameWithOctave
            for n in part.flatten().notes
            if isinstance(n, m21.note.Note)
        ]
    except Exception as e:
        log.warning("MXL 파싱 실패 %s: %s", mxl_path, e)
        return []


def evaluate():
    splits = json.loads(SPLITS.read_text())
    val_items = splits["val"][:SAMPLE_SIZE]
    accuracies = []

    with tempfile.TemporaryDirectory() as tmp:
        for item in val_items:
            label = json.loads((LABELS / f"hymn{item['hymn_id']}.json").read_text())
            image_path = Path(label["image_path"])

            gt_notes = [
                n["pitch"]
                for m in label["measures"]
                for n in m["S"]
                if n["pitch"] != "REST"
            ]

            mxl = run_audiveris(image_path, Path(tmp) / item["hymn_id"])
            if mxl is None:
                log.warning("Audiveris 실패: hymn%s", item["hymn_id"])
                accuracies.append(0.0)
                continue

            pred_notes = extract_soprano_pitches(mxl)
            acc = pitch_accuracy(pred_notes, gt_notes)
            accuracies.append(acc)
            log.info("hymn%s: GT=%d, Pred=%d, acc=%.1f%%",
                     item["hymn_id"], len(gt_notes), len(pred_notes), acc * 100)

    mean_acc = sum(accuracies) / len(accuracies) if accuracies else 0.0
    print(f"\n=== Audiveris 기준선 정확도 (n={len(accuracies)}) ===")
    print(f"평균 소프라노 음표 정확도: {mean_acc:.1%}")
    print("결론:", "자체 학습 진행" if mean_acc < 0.95 else "Audiveris 충분 — 재검토 필요")
    return mean_acc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    evaluate()
```

- [ ] **Step 2: 기준선 평가 실행**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore
/opt/miniconda3/envs/aiscore/bin/python training/scripts/baseline_eval.py
```
Expected: `평균 소프라노 음표 정확도: 65.x%` (이전 실측 결과 기준)

- [ ] **Step 3: 결과 기록 및 커밋**

```bash
git add training/scripts/baseline_eval.py
git commit -m "feat(training): Audiveris 기준선 평가 스크립트 (≈65% 확인)"
```

---

## Task 3: CRNN 모델 정의 + 학습 루프

**Goal:** ResNet18 인코더 + 4성부 CTC 헤드 CRNN 모델을 정의하고 MPS에서 학습한다.

**Files:**
- Create: `training/scripts/train_omr.py`
- Create: `tests/training/test_vocab.py`

**Interfaces:**
- Consumes: `training/data/labels/`, `training/data/splits.json`
- Produces: `training/models/omr_crnn_best.pt`
- Produces:
  - `NoteVocab` 클래스 (토큰화 / 디코딩)
  - `OmrCRNN` 클래스 (`nn.Module`, `forward(img) -> dict[str, Tensor]`)

**어휘(Vocabulary) 설계:**
- 음표 토큰: `REST`, `C2`~`B6` + 변음 (`C-2`, `C#2`, `D-2` ...) ≈ 80개
- 지속시간 토큰: `0.25` `0.5` `1.0` `1.5` `2.0` `2.5` `3.0` `4.0` — 음표 뒤에 붙임
- 타이 토큰: `TIE_S`, `TIE_E`
- 특수 토큰: `<BLK>` (CTC blank), `<EOS>`
- 최종 vocab 크기 ≈ 170

- [ ] **Step 1: 어휘 테스트 작성**

```python
# tests/training/test_vocab.py
import pytest


def test_vocab_encode_decode_roundtrip():
    from training.scripts.train_omr import NoteVocab
    vocab = NoteVocab()
    notes = [
        {"pitch": "A-4", "duration": 1.0, "tie_start": False, "tie_end": False},
        {"pitch": "REST", "duration": 2.0, "tie_start": False, "tie_end": False},
        {"pitch": "G4",   "duration": 0.5, "tie_start": True,  "tie_end": False},
    ]
    tokens = vocab.encode(notes)
    decoded = vocab.decode(tokens)
    assert decoded[0]["pitch"] == "A-4"
    assert decoded[0]["duration"] == 1.0
    assert decoded[1]["pitch"] == "REST"
    assert decoded[2]["tie_start"] is True


def test_vocab_blank_index_is_zero():
    from training.scripts.train_omr import NoteVocab
    vocab = NoteVocab()
    assert vocab.blank_idx == 0


def test_vocab_size_reasonable():
    from training.scripts.train_omr import NoteVocab
    vocab = NoteVocab()
    assert 100 < vocab.size < 300
```

- [ ] **Step 2: 어휘 테스트 실패 확인**

```bash
/opt/miniconda3/envs/aiscore/bin/python -m pytest tests/training/test_vocab.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `training/scripts/train_omr.py` 구현**

```python
"""CRNN OMR 모델 정의 + 학습 루프."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

import torch
import torch.nn as nn
import torchvision.models as tv_models
import torchvision.transforms as T
from PIL import Image
from torch.utils.data import Dataset, DataLoader

log = logging.getLogger(__name__)

# ── 경로 상수 ──────────────────────────────────────────────────────────────────
SPLITS_PATH = Path("training/data/splits.json")
LABELS_DIR  = Path("training/data/labels")
MODELS_DIR  = Path("training/models")

VOICE_ORDER = ("S", "A", "T", "B")
IMG_W, IMG_H = 256, 1024  # 학습 시 리사이즈 (가로×세로)
BATCH_SIZE   = 8
EPOCHS       = 30
LR           = 1e-4


# ── Vocabulary ────────────────────────────────────────────────────────────────

def _build_pitch_list() -> list[str]:
    steps = ["C", "D", "E", "F", "G", "A", "B"]
    accidentals = ["", "-", "#"]
    pitches = ["REST"]
    for octave in range(2, 7):
        for step in steps:
            for acc in accidentals:
                pitches.append(f"{step}{acc}{octave}")
    return pitches


class NoteVocab:
    """음표 시퀀스 ↔ 토큰 인덱스 변환."""

    DURATIONS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

    def __init__(self) -> None:
        pitches = _build_pitch_list()
        dur_strs = [f"DUR_{d}" for d in self.DURATIONS]
        specials = ["<BLK>", "<EOS>", "TIE_S", "TIE_E"]
        tokens = specials + pitches + dur_strs
        self._tok2idx: dict[str, int] = {t: i for i, t in enumerate(tokens)}
        self._idx2tok: dict[int, str] = {i: t for t, i in self._tok2idx.items()}

    @property
    def blank_idx(self) -> int:
        return self._tok2idx["<BLK>"]

    @property
    def eos_idx(self) -> int:
        return self._tok2idx["<EOS>"]

    @property
    def size(self) -> int:
        return len(self._tok2idx)

    def encode(self, notes: list[dict]) -> list[int]:
        """음표 list → 토큰 인덱스 list."""
        indices = []
        for n in notes:
            # pitch
            p = n["pitch"]
            if p not in self._tok2idx:
                log.warning("미등록 pitch 무시: %s", p)
                continue
            indices.append(self._tok2idx[p])
            # duration (nearest)
            dur = min(self.DURATIONS, key=lambda d: abs(d - n["duration"]))
            indices.append(self._tok2idx[f"DUR_{dur}"])
            # tie
            if n.get("tie_start"):
                indices.append(self._tok2idx["TIE_S"])
            if n.get("tie_end"):
                indices.append(self._tok2idx["TIE_E"])
        indices.append(self.eos_idx)
        return indices

    def decode(self, indices: list[int]) -> list[dict]:
        """토큰 인덱스 list → 음표 list (CTC 중복 제거 포함)."""
        notes: list[dict] = []
        cur: dict | None = None
        for idx in indices:
            tok = self._idx2tok.get(idx, "")
            if tok in ("<BLK>", "<EOS>"):
                continue
            if tok.startswith("DUR_"):
                if cur is not None:
                    cur["duration"] = float(tok[4:])
            elif tok == "TIE_S":
                if cur is not None:
                    cur["tie_start"] = True
            elif tok == "TIE_E":
                if cur is not None:
                    cur["tie_end"] = True
            else:  # pitch token
                if cur is not None:
                    notes.append(cur)
                cur = {"pitch": tok, "duration": 1.0, "tie_start": False, "tie_end": False}
        if cur is not None:
            notes.append(cur)
        return notes


# ── Dataset ───────────────────────────────────────────────────────────────────

class HymnDataset(Dataset):
    """찬송가 이미지 + 4성부 노트 시퀀스 데이터셋."""

    _transform = T.Compose([
        T.Grayscale(num_output_channels=3),
        T.Resize((IMG_H, IMG_W)),
        T.ToTensor(),
        T.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
    ])

    def __init__(self, items: list[dict], vocab: NoteVocab) -> None:
        self._items = items
        self._vocab = vocab

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> dict:
        item = self._items[idx]
        label = json.loads(Path(item["label_path"]).read_text())
        img = Image.open(label["image_path"]).convert("RGB")
        img_tensor = self._transform(img)

        targets: dict[str, list[int]] = {}
        for voice in VOICE_ORDER:
            notes = [n for m in label["measures"] for n in m[voice]]
            targets[voice] = self._vocab.encode(notes)

        return {"image": img_tensor, "targets": targets, "hymn_id": label["hymn_id"]}


def collate_fn(batch: list[dict]) -> dict:
    """가변 길이 시퀀스 패딩."""
    images = torch.stack([b["image"] for b in batch])
    targets: dict[str, list] = {v: [] for v in VOICE_ORDER}
    target_lengths: dict[str, list] = {v: [] for v in VOICE_ORDER}
    for b in batch:
        for voice in VOICE_ORDER:
            seq = b["targets"][voice]
            targets[voice].append(torch.tensor(seq, dtype=torch.long))
            target_lengths[voice].append(len(seq))
    padded: dict[str, torch.Tensor] = {}
    for voice in VOICE_ORDER:
        padded[voice] = torch.nn.utils.rnn.pad_sequence(
            targets[voice], batch_first=True, padding_value=0
        )
    return {
        "image": images,
        "targets": padded,
        "target_lengths": {v: torch.tensor(target_lengths[v]) for v in VOICE_ORDER},
    }


# ── Model ─────────────────────────────────────────────────────────────────────

class OmrCRNN(nn.Module):
    """ResNet18 인코더 + 4성부 독립 BiLSTM CTC 헤드."""

    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        backbone = tv_models.resnet18(weights=tv_models.ResNet18_Weights.DEFAULT)
        # 마지막 FC + avgpool 제거, spatial feature map 유지
        self.encoder = nn.Sequential(*list(backbone.children())[:-2])
        enc_channels = 512

        # 세로 압축 후 BiLSTM
        self.pool_h = nn.AdaptiveAvgPool2d((1, None))  # (B, C, 1, W')
        self.lstm = nn.LSTM(
            input_size=enc_channels,
            hidden_size=256,
            num_layers=2,
            bidirectional=True,
            batch_first=True,
        )
        # 4성부 독립 헤드
        self.heads = nn.ModuleDict({
            voice: nn.Linear(512, vocab_size) for voice in VOICE_ORDER
        })

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        feat = self.encoder(x)           # (B, 512, H', W')
        feat = self.pool_h(feat)         # (B, 512, 1, W')
        feat = feat.squeeze(2)           # (B, 512, W')
        feat = feat.permute(0, 2, 1)     # (B, W', 512)
        out, _ = self.lstm(feat)         # (B, W', 512)
        logits: dict[str, torch.Tensor] = {}
        for voice in VOICE_ORDER:
            lgt = self.heads[voice](out)  # (B, W', V)
            logits[voice] = lgt.permute(1, 0, 2)  # (W', B, V) for CTC
        return logits


# ── Training ──────────────────────────────────────────────────────────────────

def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def train(epochs: int = EPOCHS) -> None:
    device = get_device()
    log.info("디바이스: %s", device)

    splits = json.loads(SPLITS_PATH.read_text())
    vocab = NoteVocab()

    train_ds = HymnDataset(splits["train"], vocab)
    val_ds   = HymnDataset(splits["val"],   vocab)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                              collate_fn=collate_fn, num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False,
                              collate_fn=collate_fn, num_workers=0)

    model = OmrCRNN(vocab.size).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    ctc_loss = nn.CTCLoss(blank=vocab.blank_idx, zero_infinity=True)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    best_val_loss = float("inf")

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for batch in train_loader:
            images = batch["image"].to(device)
            logits = model(images)
            input_lengths = torch.full(
                (images.size(0),), logits["S"].size(0), dtype=torch.long
            )
            loss = torch.tensor(0.0, device=device)
            for voice in VOICE_ORDER:
                tgt = batch["targets"][voice].to(device)
                tgt_len = batch["target_lengths"][voice].to(device)
                lgt = logits[voice]  # (T, B, V)
                loss = loss + ctc_loss(
                    lgt.log_softmax(dim=-1), tgt, input_lengths, tgt_len
                )
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            train_loss += loss.item()

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                logits = model(images)
                input_lengths = torch.full(
                    (images.size(0),), logits["S"].size(0), dtype=torch.long
                )
                loss = torch.tensor(0.0, device=device)
                for voice in VOICE_ORDER:
                    tgt = batch["targets"][voice].to(device)
                    tgt_len = batch["target_lengths"][voice].to(device)
                    loss = loss + ctc_loss(
                        logits[voice].log_softmax(dim=-1), tgt, input_lengths, tgt_len
                    )
                val_loss += loss.item()

        avg_train = train_loss / len(train_loader)
        avg_val   = val_loss   / len(val_loader)
        log.info("Epoch %d/%d | train=%.4f val=%.4f", epoch, epochs, avg_train, avg_val)
        scheduler.step(avg_val)

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            ckpt = {
                "epoch": epoch, "model_state": model.state_dict(),
                "vocab_size": vocab.size, "val_loss": avg_val,
            }
            torch.save(ckpt, MODELS_DIR / "omr_crnn_best.pt")
            log.info("체크포인트 저장 (val=%.4f)", avg_val)

    log.info("학습 완료. 최종 val_loss=%.4f", best_val_loss)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    train()
```

- [ ] **Step 4: 어휘 테스트 통과 확인**

```bash
/opt/miniconda3/envs/aiscore/bin/python -m pytest tests/training/test_vocab.py -v
```
Expected: 3 passed

- [ ] **Step 5: 모델 스모크 테스트 (단일 배치)**

```bash
/opt/miniconda3/envs/aiscore/bin/python -c "
import torch, json
from pathlib import Path
from training.scripts.train_omr import OmrCRNN, NoteVocab, HymnDataset, collate_fn, VOICE_ORDER
splits = json.loads(Path('training/data/splits.json').read_text())
vocab = NoteVocab()
ds = HymnDataset(splits['train'][:2], vocab)
batch = collate_fn([ds[0], ds[1]])
model = OmrCRNN(vocab.size)
logits = model(batch['image'])
for v in VOICE_ORDER:
    print(v, logits[v].shape)  # (T, B, V) 기대
print('OK')
"
```
Expected: `S torch.Size([T, 2, 170~]) ... OK`

- [ ] **Step 6: 학습 실행 (30 epoch, MPS)**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore
/opt/miniconda3/envs/aiscore/bin/python training/scripts/train_omr.py
```
진행 중 `training/models/omr_crnn_best.pt` 생성 확인.

- [ ] **Step 7: 커밋**

```bash
git add training/scripts/train_omr.py tests/training/test_vocab.py
git commit -m "feat(training): CRNN OMR 모델 정의 + 4성부 CTC 학습 루프"
```

---

## Task 4: 노트북 래퍼 작성

**Goal:** 실험 재현과 시각화를 위한 Jupyter 노트북 작성.

**Files:**
- Create: `training/notebooks/01_data_prep.ipynb`
- Create: `training/notebooks/02_train_omr.ipynb`

**Note:** 노트북은 스크립트 `data_prep.py` / `train_omr.py`를 `import`하거나 `%run`으로 실행하는 얇은 래퍼다. 비즈니스 로직 중복 금지.

- [ ] **Step 1: 01_data_prep.ipynb 작성**

셀 구조:
```
[셀 1] # 데이터 준비
from training.scripts.data_prep import build_dataset, parse_xml
build_dataset()

[셀 2] # 샘플 시각화
import json
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt

label = json.loads(Path("training/data/labels/hymn001.json").read_text())
img = Image.open(label["image_path"])
plt.imshow(img, cmap="gray"); plt.title("hymn001"); plt.show()
print(f"마디 수: {len(label['measures'])}")
print("M2 소프라노:", label["measures"][1]["S"])

[셀 3] # 분할 통계
splits = json.loads(Path("training/data/splits.json").read_text())
for k, v in splits.items():
    print(f"{k}: {len(v)}개")
```

- [ ] **Step 2: 02_train_omr.ipynb 작성**

셀 구조:
```
[셀 1] # 학습
from training.scripts.train_omr import train
train(epochs=30)

[셀 2] # 손실 곡선 (checkpoint에서)
import torch, matplotlib.pyplot as plt
ckpt = torch.load("training/models/omr_crnn_best.pt", map_location="cpu")
print(f"Best val loss: {ckpt['val_loss']:.4f} (epoch {ckpt['epoch']})")

[셀 3] # 추론 샘플
import json
from pathlib import Path
from PIL import Image
import torchvision.transforms as T
import torch
from training.scripts.train_omr import OmrCRNN, NoteVocab, IMG_H, IMG_W

vocab = NoteVocab()
model = OmrCRNN(vocab.size)
ckpt = torch.load("training/models/omr_crnn_best.pt", map_location="cpu")
model.load_state_dict(ckpt["model_state"]); model.eval()

label = json.loads(Path("training/data/labels/hymn001.json").read_text())
img = Image.open(label["image_path"]).convert("RGB")
transform = T.Compose([
    T.Grayscale(3), T.Resize((IMG_H, IMG_W)), T.ToTensor(),
    T.Normalize([0.5]*3, [0.5]*3)
])
x = transform(img).unsqueeze(0)
with torch.no_grad():
    logits = model(x)
pred_idx = logits["S"].argmax(dim=-1)[:, 0].tolist()
print("소프라노 예측:", vocab.decode(pred_idx)[:5])
print("소프라노 정답:", label["measures"][1]["S"][:3])
```

- [ ] **Step 3: 노트북 저장 확인**

```bash
ls training/notebooks/
```
Expected: `01_data_prep.ipynb  02_train_omr.ipynb`

- [ ] **Step 4: 커밋**

```bash
git add training/notebooks/
git commit -m "feat(training): 데이터 준비·학습 Jupyter 노트북 추가"
```

---

## Task 5: 백엔드 DL-OMR 어댑터

**Goal:** 학습된 `omr_crnn_best.pt`를 로드하여 `OmrPort.recognize()` 인터페이스로 연결.

**Files:**
- Create: `backend/app/stages/omr/dl_omr_adapter.py`
- Create: `tests/stages/omr/test_dl_omr_adapter.py`

**Interfaces:**
- Consumes: `training/models/omr_crnn_best.pt` (런타임)
- Implements: `OmrPort.recognize(image_path: Path) -> Path`
- Produces: MusicXML `.xml` 파일 (JSON → music21 → MusicXML 변환)

**중요:** `training/` 모듈을 `backend/`에서 직접 import하지 않는다. 모델 아키텍처 코드(`OmrCRNN`, `NoteVocab`)를 `dl_omr_adapter.py` 안에 복사하거나 별도 공유 패키지로 분리한다. 여기서는 간결성을 위해 인라인 복사 방식 사용.

- [ ] **Step 1: 어댑터 테스트 작성**

```python
# tests/stages/omr/test_dl_omr_adapter.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_dl_omr_adapter_implements_omr_port():
    from app.stages.omr.dl_omr_adapter import DlOmrAdapter
    from app.domain.ports import OmrPort
    # 모델 없이 인스턴스 생성 가능 (model_path=None)
    adapter = DlOmrAdapter(work_dir=Path("/tmp"), model_path=None)
    assert isinstance(adapter, OmrPort)


def test_dl_omr_adapter_no_model_raises(tmp_path):
    from app.stages.omr.dl_omr_adapter import DlOmrAdapter
    adapter = DlOmrAdapter(work_dir=tmp_path, model_path=None)
    dummy_img = tmp_path / "test.png"
    dummy_img.write_bytes(b"")
    with pytest.raises(RuntimeError, match="모델 가중치"):
        adapter.recognize(dummy_img)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore/backend
/opt/miniconda3/envs/aiscore/bin/python -m pytest ../tests/stages/omr/test_dl_omr_adapter.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `dl_omr_adapter.py` 구현**

```python
# backend/app/stages/omr/dl_omr_adapter.py
"""DL-OMR 어댑터 — 학습된 CRNN 모델로 OmrPort 구현."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import music21 as m21
import torch
import torch.nn as nn
import torchvision.transforms as T
from PIL import Image

log = logging.getLogger(__name__)

VOICE_ORDER = ("S", "A", "T", "B")
IMG_W, IMG_H = 256, 1024

# ── Vocab (training/scripts/train_omr.py와 동일 구현 유지) ────────────────────

def _build_pitch_list() -> list[str]:
    steps = ["C", "D", "E", "F", "G", "A", "B"]
    accidentals = ["", "-", "#"]
    pitches = ["REST"]
    for octave in range(2, 7):
        for step in steps:
            for acc in accidentals:
                pitches.append(f"{step}{acc}{octave}")
    return pitches


class _NoteVocab:
    DURATIONS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]

    def __init__(self) -> None:
        pitches = _build_pitch_list()
        dur_strs = [f"DUR_{d}" for d in self.DURATIONS]
        specials = ["<BLK>", "<EOS>", "TIE_S", "TIE_E"]
        tokens = specials + pitches + dur_strs
        self._tok2idx: dict[str, int] = {t: i for i, t in enumerate(tokens)}
        self._idx2tok: dict[int, str] = {i: t for t, i in self._tok2idx.items()}

    @property
    def blank_idx(self) -> int:
        return self._tok2idx["<BLK>"]

    @property
    def size(self) -> int:
        return len(self._tok2idx)

    def decode(self, indices: list[int]) -> list[dict]:
        notes: list[dict] = []
        cur: dict | None = None
        prev = None
        for idx in indices:
            if idx == prev:  # CTC 중복 제거
                prev = idx
                continue
            prev = idx
            tok = self._idx2tok.get(idx, "")
            if tok in ("<BLK>", "<EOS>"):
                continue
            if tok.startswith("DUR_"):
                if cur is not None:
                    cur["duration"] = float(tok[4:])
            elif tok == "TIE_S":
                if cur is not None:
                    cur["tie_start"] = True
            elif tok == "TIE_E":
                if cur is not None:
                    cur["tie_end"] = True
            else:
                if cur is not None:
                    notes.append(cur)
                cur = {"pitch": tok, "duration": 1.0, "tie_start": False, "tie_end": False}
        if cur is not None:
            notes.append(cur)
        return notes


# ── Model (training/scripts/train_omr.py와 동일 아키텍처) ─────────────────────

class _OmrCRNN(nn.Module):
    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        import torchvision.models as tv_models
        backbone = tv_models.resnet18(weights=None)
        self.encoder = nn.Sequential(*list(backbone.children())[:-2])
        self.pool_h = nn.AdaptiveAvgPool2d((1, None))
        self.lstm = nn.LSTM(512, 256, num_layers=2, bidirectional=True, batch_first=True)
        self.heads = nn.ModuleDict({v: nn.Linear(512, vocab_size) for v in VOICE_ORDER})

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        feat = self.encoder(x)
        feat = self.pool_h(feat).squeeze(2).permute(0, 2, 1)
        out, _ = self.lstm(feat)
        return {v: self.heads[v](out).permute(1, 0, 2) for v in VOICE_ORDER}


# ── JSON → MusicXML 변환 ───────────────────────────────────────────────────────

def _notes_to_musicxml(
    voice_notes: dict[str, list[dict]],
    out_path: Path,
    time_sig: str = "4/4",
) -> Path:
    score = m21.stream.Score()
    voice_map = {"S": "Soprano", "A": "Alto", "T": "Tenor", "B": "Bass"}
    for voice_name in VOICE_ORDER:
        part = m21.stream.Part()
        part.partName = voice_map[voice_name]
        measure = m21.stream.Measure(number=1)
        for n_dict in voice_notes[voice_name]:
            if n_dict["pitch"] == "REST":
                n = m21.note.Rest(quarterLength=n_dict["duration"])
            else:
                n = m21.note.Note(n_dict["pitch"], quarterLength=n_dict["duration"])
                if n_dict.get("tie_start"):
                    n.tie = m21.tie.Tie("start")
            measure.append(n)
        part.append(measure)
        score.append(part)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(out_path))
    return out_path


# ── Adapter ───────────────────────────────────────────────────────────────────

class DlOmrAdapter:
    """학습된 CRNN 모델로 OmrPort 구현."""

    _transform = T.Compose([
        T.Grayscale(num_output_channels=3),
        T.Resize((IMG_H, IMG_W)),
        T.ToTensor(),
        T.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
    ])

    def __init__(self, work_dir: Path, model_path: Path | None) -> None:
        self._work_dir = work_dir
        self._model: _OmrCRNN | None = None
        self._vocab = _NoteVocab()

        if model_path and model_path.exists():
            ckpt = torch.load(model_path, map_location="cpu")
            self._model = _OmrCRNN(self._vocab.size)
            self._model.load_state_dict(ckpt["model_state"])
            self._model.eval()
            log.info("DL-OMR 모델 로드 완료: %s (epoch=%s, val_loss=%.4f)",
                     model_path, ckpt.get("epoch"), ckpt.get("val_loss", 0))
        elif model_path:
            log.warning("모델 가중치 없음: %s", model_path)

    def recognize(self, image_path: Path) -> Path:
        if self._model is None:
            raise RuntimeError("모델 가중치가 없습니다. training/models/omr_crnn_best.pt 필요")

        img = Image.open(image_path).convert("RGB")
        x = self._transform(img).unsqueeze(0)

        with torch.no_grad():
            logits = self._model(x)

        voice_notes: dict[str, list[dict]] = {}
        for voice in VOICE_ORDER:
            pred_idx = logits[voice].argmax(dim=-1)[:, 0].tolist()
            voice_notes[voice] = self._vocab.decode(pred_idx)

        job_dir = self._work_dir / image_path.stem
        out_path = job_dir / f"{image_path.stem}.xml"
        return _notes_to_musicxml(voice_notes, out_path)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore/backend
/opt/miniconda3/envs/aiscore/bin/python -m pytest ../tests/stages/omr/test_dl_omr_adapter.py -v
```
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore
git add backend/app/stages/omr/dl_omr_adapter.py tests/stages/omr/test_dl_omr_adapter.py
git commit -m "feat(omr): DlOmrAdapter — 학습된 CRNN 모델 OmrPort 연결"
```

---

## Task 6: E2E 검증 — 이미지 → OSMD 렌더링

**Goal:** 학습된 모델로 실제 이미지를 처리하여 OSMD에서 악보가 렌더링되는지 확인.

**Files:**
- Modify: `backend/app/core/config.py` — `DL_OMR_MODEL_PATH` 설정 추가
- Modify: `backend/app/orchestration/` — `DlOmrAdapter` 활성화 옵션

- [ ] **Step 1: config에 DL_OMR 모델 경로 추가**

`backend/app/core/config.py`에서 `omr_model_path` 함수를 찾아 DL 모델 경로 반환 추가:
```python
# 기존 omr_model_path() 함수에 추가하거나, 새 함수 추가
def dl_omr_model_path() -> Path | None:
    p = Path(os.getenv("DL_OMR_MODEL_PATH", "training/models/omr_crnn_best.pt"))
    return p if p.exists() else None
```

- [ ] **Step 2: 백엔드 수동 E2E 테스트**

```bash
cd /Users/sknoh/Documents/Workspace/aiscore
/opt/miniconda3/envs/aiscore/bin/python -c "
from pathlib import Path
from app.stages.omr.dl_omr_adapter import DlOmrAdapter
import tempfile, sys
sys.path.insert(0, 'backend')

with tempfile.TemporaryDirectory() as tmp:
    adapter = DlOmrAdapter(
        work_dir=Path(tmp),
        model_path=Path('training/models/omr_crnn_best.pt')
    )
    result = adapter.recognize(Path('score_images/png/hymn001_Normal.png'))
    print('MusicXML 생성:', result)
    print('파일 크기:', result.stat().st_size, 'bytes')
" 2>&1 | tail -5
```
Expected: `MusicXML 생성: /tmp/.../hymn001_Normal.xml` + 파일 크기 > 0

- [ ] **Step 3: 프론트엔드 E2E 테스트**

```bash
# 터미널 1: 백엔드
cd backend && /opt/miniconda3/envs/aiscore/bin/uvicorn app.main:app --reload

# 터미널 2: 프론트엔드
cd frontend && npm run dev
```
1. http://localhost:3000 접속
2. `score_images/png/hymn001_Normal.png` 업로드
3. 잡 페이지에서 OSMD 악보 렌더링 확인
4. 오디오 플레이어 재생 확인

- [ ] **Step 4: 최종 커밋**

```bash
git add backend/app/core/config.py
git commit -m "feat(omr): Plan 1B E2E 검증 완료 — DL-OMR 파이프라인 연결"
```

---

## 자체 검토

### Spec 커버리지

| ROADMAP 태스크 | 구현 태스크 |
|---|---|
| `01_data_prep.ipynb` — 644쌍 페어링 + JSON 라벨 | Task 1 + Task 4 |
| `02_train_omr.ipynb` — 모델 정의 + 학습 | Task 3 + Task 4 |
| 기존 모델 사전 검증 (Audiveris 65%) | Task 2 |
| `data_prep.py` + `train_omr.py` | Task 1, 3 |
| `dl_omr_adapter.py` — OmrPort 교체 | Task 5 |
| E2E 검증 | Task 6 |

### 잠재적 이슈

- **학습 수렴 여부**: 644샘플로 95% 정확도 달성 여부 불확실. Task 3 완료 후 val_loss 추이 확인 후 데이터 증강(회전·밝기 변환) 추가 이터레이션 필요할 수 있음.
- **키 시그니처 처리**: `A-4`(Ab4) 등 음이름에 임시표 포함 — Vocab에 이미 반영됨.
- **다페이지 이미지**: 2400px 이상 이미지(16개)는 Resize로 압축 → 정보 손실. 추후 페이지 분할 전처리 추가 고려.
