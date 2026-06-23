"""CRNN OMR 모델 정의 + 학습 루프."""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# ── MPS Fallback (torch import 이전) ────────────────────────────────────────
if sys.platform == "darwin":
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch
import torch.nn as nn
import torchvision.models as tv_models
import torchvision.transforms as T
from PIL import Image
from torch.utils.data import Dataset, DataLoader

log = logging.getLogger(__name__)

# ── 경로 상수 ──────────────────────────────────────────────────────────────────
_REPO_ROOT  = Path(__file__).resolve().parents[2]
SPLITS_PATH       = _REPO_ROOT / "training/data/splits.json"
SPLITS_STAFF_PATH = _REPO_ROOT / "training/data/splits_staff.json"
LABELS_DIR        = _REPO_ROOT / "training/data/labels"
MODELS_DIR        = _REPO_ROOT / "training/models"

VOICE_ORDER = ("S", "A", "T", "B")
TREBLE_VOICES = ("S", "A")
BASS_VOICES   = ("T", "B")

# 구형 시스템-레벨 모델 설정
IMG_W, IMG_H = 2048, 128  # landscape, T = 2048/16 = 128 frames
BATCH_SIZE   = 8
EPOCHS       = 30
LR           = 1e-4

# 신형 스태프-레벨 모델 설정
STAFF_IMG_W  = 1600
STAFF_IMG_H  = 64
STAFF_BATCH  = 8


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
                log.debug("미등록 pitch 무시: %s", p)
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
        # EOS는 CTC target에 포함하지 않음 (CTC blank만 사용)
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
        T.Resize((IMG_H, IMG_W)),  # (H, W) = (128, 2048)
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


# ── Staff-level Dataset ───────────────────────────────────────────────────────

class StaffDataset(Dataset):
    """스태프 크롭 이미지 + treble(S+A) 또는 bass(T+B) 노트 시퀀스."""

    def __init__(self, items: list[dict], vocab: NoteVocab) -> None:
        self._items = items
        self._vocab = vocab
        self._transform = T.Compose([
            T.Grayscale(num_output_channels=3),
            T.Resize((STAFF_IMG_H, STAFF_IMG_W)),
            T.ToTensor(),
            T.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ])

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> dict:
        item = self._items[idx]
        label = json.loads(Path(item["label_path"]).read_text())
        img = Image.open(label["image_path"]).convert("RGB")
        img_tensor = self._transform(img)

        staff = label.get("staff", "treble")
        voices = TREBLE_VOICES if staff == "treble" else BASS_VOICES
        targets: dict[str, list[int]] = {}
        for voice in voices:
            notes = [n for m in label["measures"] for n in m[voice]]
            targets[voice] = self._vocab.encode(notes)

        return {"image": img_tensor, "targets": targets, "staff": staff,
                "hymn_id": label["hymn_id"]}


def staff_collate_fn(batch: list[dict]) -> dict:
    images = torch.stack([b["image"] for b in batch])
    staff = batch[0]["staff"]
    voices = TREBLE_VOICES if staff == "treble" else BASS_VOICES

    targets: dict[str, list] = {v: [] for v in voices}
    target_lengths: dict[str, list] = {v: [] for v in voices}
    for b in batch:
        for voice in voices:
            seq = b["targets"][voice]
            targets[voice].append(torch.tensor(seq, dtype=torch.long))
            target_lengths[voice].append(len(seq))

    padded = {
        v: torch.nn.utils.rnn.pad_sequence(targets[v], batch_first=True, padding_value=0)
        for v in voices
    }
    return {
        "image": images,
        "targets": padded,
        "target_lengths": {v: torch.tensor(target_lengths[v]) for v in voices},
        "staff": staff,
    }


# ── Model ─────────────────────────────────────────────────────────────────────

class OmrCRNN(nn.Module):
    """ResNet18 인코더 + 4성부 독립 BiLSTM CTC 헤드."""

    def __init__(self, vocab_size: int) -> None:
        super().__init__()
        backbone = tv_models.resnet18(weights=tv_models.ResNet18_Weights.DEFAULT)
        backbone.maxpool = nn.Identity()  # stride 32→16, T = IMG_W/16 = 128
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


# ── StaffCRNN ─────────────────────────────────────────────────────────────────

def _make_height_preserving_resnet18() -> nn.Module:
    """ResNet18에서 layer2~4의 첫 conv stride를 (1,2)로 변경.

    기본 stride (2,2) → (1,2): 가로만 다운샘플, H' 보존.
    입력 H=64 기준: H' = 64/2 = 32 (layer1 stride만 적용).
    T = W/2 = 1600/2 = 800 → layer1~4 거치면 1600/16=100 frames.
    """
    backbone = tv_models.resnet18(weights=tv_models.ResNet18_Weights.DEFAULT)
    backbone.maxpool = nn.Identity()  # maxpool 제거로 초기 stride 32→16

    for layer in (backbone.layer2, backbone.layer3, backbone.layer4):
        for module in layer.modules():
            if isinstance(module, nn.Conv2d) and module.stride == (2, 2):
                module.stride = (1, 2)
            if isinstance(module, nn.BatchNorm2d):
                pass
        # Residual shortcut도 stride 수정
        if hasattr(layer[0], "downsample") and layer[0].downsample is not None:
            for module in layer[0].downsample.modules():
                if isinstance(module, nn.Conv2d) and module.stride == (2, 2):
                    module.stride = (1, 2)

    return nn.Sequential(*list(backbone.children())[:-2])


class StaffCRNN(nn.Module):
    """스태프(treble 또는 bass) 단위 CRNN.

    아키텍처:
      ResNet18 (height-preserving) → (B, 512, H', T')
      channel_reduce 512→64        → (B, 64,  H', T')
      flatten_h (B,64,H',T')       → (B, T',  64*H')
      projection 64*H'→256         → (B, T',  256)
      BiLSTM 256→512               → (B, T',  512)
      heads: treble={S,A} or bass={T,B}

    H' 계산 (STAFF_IMG_H=64):
      Conv1 stride=2 → 32, maxpool=Identity → 32
      layer2~4 stride=(1,2) → H 그대로 32
      따라서 C*H = 64*32 = 2048 고정.
    """

    _PROJ_IN = 64 * 32  # 2048: channel_reduce C × H' at H=64 input

    def __init__(self, vocab_size: int, staff: str) -> None:
        super().__init__()
        assert staff in ("treble", "bass")
        self.staff  = staff
        self.voices = TREBLE_VOICES if staff == "treble" else BASS_VOICES

        self.encoder        = _make_height_preserving_resnet18()
        self.channel_reduce = nn.Conv2d(512, 64, kernel_size=1)
        self.projection     = nn.Linear(self._PROJ_IN, 256)
        self.lstm = nn.LSTM(
            input_size=256,
            hidden_size=256,
            num_layers=2,
            bidirectional=True,
            batch_first=True,
        )
        self.heads = nn.ModuleDict({
            v: nn.Linear(512, vocab_size) for v in self.voices
        })

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        feat = self.encoder(x)              # (B, 512, H', T')
        feat = self.channel_reduce(feat)    # (B, 64,  H', T')
        B, C, H, TT = feat.shape
        feat = feat.permute(0, 3, 1, 2)    # (B, T', C, H')
        feat = feat.reshape(B, TT, C * H)  # (B, T', C*H')
        feat = self.projection(feat)        # (B, T', 256)
        out, _ = self.lstm(feat)            # (B, T', 512)

        logits: dict[str, torch.Tensor] = {}
        for voice in self.voices:
            lgt = self.heads[voice](out)   # (B, T', V)
            logits[voice] = lgt.permute(1, 0, 2)  # (T', B, V) for CTC
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

    n_train = len(train_ds)
    n_val   = len(val_ds)
    print(f"[학습 시작] 디바이스={device}  train={n_train}  val={n_val}  epochs={epochs}", flush=True)
    print("-" * 60, flush=True)

    import time
    t_start = time.time()

    for epoch in range(1, epochs + 1):
        t_epoch = time.time()
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
        elapsed   = time.time() - t_epoch
        saved_mark = ""

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            ckpt = {
                "epoch": epoch,
                "model_state": model.state_dict(),
                "vocab_size": vocab.size,
                "vocab_tok2idx": vocab._tok2idx,  # vocab 변경 시 decoding 오류 방지
                "val_loss": avg_val,
            }
            torch.save(ckpt, MODELS_DIR / "omr_crnn_best.pt")
            saved_mark = "  ★ 저장"

        print(
            f"Epoch {epoch:>3}/{epochs}"
            f"  train={avg_train:.4f}"
            f"  val={avg_val:.4f}"
            f"  {elapsed:.0f}s{saved_mark}",
            flush=True,
        )
        log.info("Epoch %d/%d | train=%.4f val=%.4f", epoch, epochs, avg_train, avg_val)
        scheduler.step(avg_val)

    total_min = (time.time() - t_start) / 60
    print("-" * 60, flush=True)
    print(f"[학습 완료]  best_val_loss={best_val_loss:.4f}  총 소요={total_min:.1f}분", flush=True)
    log.info("학습 완료. 최종 val_loss=%.4f", best_val_loss)


def train_staff(epochs: int = EPOCHS) -> None:
    """스태프 크롭 기반 StaffCRNN 학습."""
    device = get_device()
    log.info("디바이스: %s", device)

    splits = json.loads(SPLITS_STAFF_PATH.read_text())
    vocab  = NoteVocab()
    ctc_loss = nn.CTCLoss(blank=vocab.blank_idx, zero_infinity=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    for staff in ("treble", "bass"):
        voices = TREBLE_VOICES if staff == "treble" else BASS_VOICES

        def _filter(items: list[dict]) -> list[dict]:
            return [i for i in items if i.get("staff") == staff]

        train_ds = StaffDataset(_filter(splits["train"]), vocab)
        val_ds   = StaffDataset(_filter(splits["val"]),   vocab)
        train_loader = DataLoader(train_ds, batch_size=STAFF_BATCH, shuffle=True,
                                  collate_fn=staff_collate_fn, num_workers=0)
        val_loader   = DataLoader(val_ds,   batch_size=STAFF_BATCH, shuffle=False,
                                  collate_fn=staff_collate_fn, num_workers=0)

        model     = StaffCRNN(vocab.size, staff).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=LR)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3)
        best_val  = float("inf")

        print(f"\n[{staff.upper()} 학습 시작]  train={len(train_ds)}  val={len(val_ds)}", flush=True)
        print("-" * 60, flush=True)

        import time
        t_start = time.time()

        for epoch in range(1, epochs + 1):
            t_ep = time.time()
            model.train()
            train_loss = 0.0
            for batch in train_loader:
                images = batch["image"].to(device)
                logits = model(images)
                T_len  = logits[voices[0]].size(0)
                inp_len = torch.full((images.size(0),), T_len, dtype=torch.long)
                loss = torch.tensor(0.0, device=device)
                for v in voices:
                    tgt     = batch["targets"][v].to(device)
                    tgt_len = batch["target_lengths"][v].to(device)
                    loss    = loss + ctc_loss(logits[v].log_softmax(-1), tgt, inp_len, tgt_len)
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
                train_loss += loss.item()

            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for batch in val_loader:
                    images = batch["image"].to(device)
                    logits = model(images)
                    T_len  = logits[voices[0]].size(0)
                    inp_len = torch.full((images.size(0),), T_len, dtype=torch.long)
                    loss = torch.tensor(0.0, device=device)
                    for v in voices:
                        tgt     = batch["targets"][v].to(device)
                        tgt_len = batch["target_lengths"][v].to(device)
                        loss    = loss + ctc_loss(logits[v].log_softmax(-1), tgt, inp_len, tgt_len)
                    val_loss += loss.item()

            avg_train = train_loss / max(len(train_loader), 1)
            avg_val   = val_loss   / max(len(val_loader), 1)
            elapsed   = time.time() - t_ep
            mark = ""
            if avg_val < best_val:
                best_val = avg_val
                ckpt = {
                    "epoch": epoch, "staff": staff,
                    "model_state": model.state_dict(),
                    "vocab_size": vocab.size,
                    "vocab_tok2idx": vocab._tok2idx,
                    "val_loss": avg_val,
                }
                torch.save(ckpt, MODELS_DIR / f"staff_crnn_{staff}_best.pt")
                mark = "  ★"
            print(f"Epoch {epoch:>3}/{epochs}  train={avg_train:.4f}  val={avg_val:.4f}  {elapsed:.0f}s{mark}",
                  flush=True)
            scheduler.step(avg_val)

        total_min = (time.time() - t_start) / 60
        print("-" * 60, flush=True)
        print(f"[{staff.upper()} 완료]  best_val={best_val:.4f}  총 소요={total_min:.1f}분", flush=True)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--staff", action="store_true", help="StaffCRNN 학습 (스태프 크롭 기반)")
    args = ap.parse_args()
    if args.staff:
        train_staff()
    else:
        train()
