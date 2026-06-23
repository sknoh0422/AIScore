"""DL-OMR 어댑터 — 학습된 CRNN 모델로 OmrPort 구현.

training/ 모듈을 backend/에서 직접 import 하지 않는다.
OmrCRNN, NoteVocab 아키텍처 코드를 인라인 복사하여 사용.
모델 아키텍처는 training/scripts/train_omr.py 와 완전히 동일해야 한다.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

VOICE_ORDER = ("S", "A", "T", "B")
IMG_W, IMG_H = 2048, 128  # train_omr.py 와 동일: landscape, T = 2048/16 = 128 frames


# ── Vocab (training/scripts/train_omr.py NoteVocab 와 동일) ──────────────────

def _build_pitch_list() -> list[str]:
    """C2~B6 × 3 임시표 피치 목록 생성. train_omr.py 와 동일 구현."""
    steps = ["C", "D", "E", "F", "G", "A", "B"]
    accidentals = ["", "-", "#"]
    pitches = ["REST"]
    for octave in range(2, 7):
        for step in steps:
            for acc in accidentals:
                pitches.append(f"{step}{acc}{octave}")
    return pitches


class _NoteVocab:
    """음표 시퀀스 ↔ 토큰 인덱스 변환. train_omr.py NoteVocab 와 동일."""

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
        """토큰 인덱스 list → 음표 list. train_omr.py NoteVocab.decode 와 동일."""
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


# ── Model (training/scripts/train_omr.py OmrCRNN 와 동일 아키텍처) ─────────────

class _OmrCRNN:
    """ResNet18 인코더 + 4성부 독립 BiLSTM CTC 헤드. 지연 import 로 torch 없이도 클래스 정의 가능."""

    def __new__(cls, vocab_size: int):  # type: ignore[override]
        import torch.nn as nn
        import torchvision.models as tv_models

        class _Inner(nn.Module):
            def __init__(self, vocab_size: int) -> None:
                super().__init__()
                backbone = tv_models.resnet18(weights=None)
                backbone.maxpool = nn.Identity()  # stride 32→16, T = IMG_W/16 = 128
                self.encoder = nn.Sequential(*list(backbone.children())[:-2])
                self.pool_h = nn.AdaptiveAvgPool2d((1, None))
                self.lstm = nn.LSTM(512, 256, num_layers=2, bidirectional=True, batch_first=True)
                self.heads = nn.ModuleDict({v: nn.Linear(512, vocab_size) for v in VOICE_ORDER})

            def forward(self, x):
                feat = self.encoder(x)
                feat = self.pool_h(feat).squeeze(2).permute(0, 2, 1)
                out, _ = self.lstm(feat)
                return {v: self.heads[v](out).permute(1, 0, 2) for v in VOICE_ORDER}

        return _Inner(vocab_size)


# ── JSON → MusicXML 변환 ────────────────────────────────────────────────────────

def _notes_to_musicxml(
    voice_notes: dict[str, list[dict]],
    out_path: Path,
    time_sig: str = "4/4",
) -> Path:
    import music21 as m21

    score = m21.stream.Score()
    voice_map = {"S": "Soprano", "A": "Alto", "T": "Tenor", "B": "Bass"}
    for voice_name in VOICE_ORDER:
        part = m21.stream.Part()
        part.partName = voice_map[voice_name]
        measure = m21.stream.Measure(number=1)
        for n_dict in voice_notes.get(voice_name, []):
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


# ── Adapter ────────────────────────────────────────────────────────────────────

class DlOmrAdapter:
    """학습된 CRNN 모델로 OmrPort 를 구현하는 어댑터.

    Args:
        work_dir: 중간 파일 및 출력 MusicXML 저장 디렉터리.
        model_path: omr_crnn_best.pt 경로. None 또는 존재하지 않으면 모델 없이 초기화.
    """

    def __init__(self, work_dir: Path, model_path: Path | None) -> None:
        self._work_dir = work_dir
        self._model = None
        self._vocab = _NoteVocab()

        if model_path is not None and model_path.exists():
            import torch
            ckpt = torch.load(model_path, map_location="cpu")
            model = _OmrCRNN(self._vocab.size)
            model.load_state_dict(ckpt["model_state"])
            model.eval()
            self._model = model
            log.info(
                "DL-OMR 모델 로드 완료: %s (epoch=%s, val_loss=%.4f)",
                model_path,
                ckpt.get("epoch"),
                ckpt.get("val_loss", 0.0),
            )
        elif model_path is not None:
            log.warning("모델 가중치 없음: %s", model_path)

    def recognize(self, image_path: Path) -> Path:
        """이미지 경로를 받아 MusicXML 파일 경로를 반환한다."""
        if self._model is None:
            raise RuntimeError(
                "모델 가중치가 없습니다. training/models/omr_crnn_best.pt 필요"
            )

        import torch
        import torchvision.transforms as T
        from PIL import Image

        transform = T.Compose([
            T.Grayscale(num_output_channels=3),
            T.Resize((IMG_H, IMG_W)),
            T.ToTensor(),
            T.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ])

        img = Image.open(image_path).convert("RGB")
        x = transform(img).unsqueeze(0)  # (1, 3, H, W)

        with torch.no_grad():
            logits = self._model(x)

        voice_notes: dict[str, list[dict]] = {}
        for voice in VOICE_ORDER:
            # logits[voice]: (T, B, V) → argmax over V → (T, B) → 첫 배치
            pred_idx = logits[voice].argmax(dim=-1)[:, 0].tolist()
            voice_notes[voice] = self._vocab.decode(pred_idx)

        job_dir = self._work_dir / image_path.stem
        out_path = job_dir / f"{image_path.stem}.xml"
        return _notes_to_musicxml(voice_notes, out_path)
