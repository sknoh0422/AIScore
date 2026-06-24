"""소규모 검증 실험 — 높이 필터(≤400px) + H=256 resize, 50샘플 10 epoch.

목적: mode collapse 해소 여부 확인 (pitch 토큰이 예측되는지).
결과가 좋으면 전체 학습에 동일 설정 적용.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path

if sys.platform == "darwin":
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T
import warnings
warnings.filterwarnings("ignore")

from PIL import Image
from torch.utils.data import Dataset, DataLoader

from training.scripts.train_omr import (
    NoteVocab, OmrCRNN, collate_fn, VOICE_ORDER,
    SPLITS_PATH,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

MAX_H = 400       # 높이 필터: 경계탐지 실패 크롭 제거
IMG_H_EXP = 256   # 기존 128 → 256 (pitch 수직 해상도 개선)
IMG_W_EXP = 2048  # T = 2048/16 = 128 frames (unchanged)


def _make_transform(img_h: int, img_w: int) -> T.Compose:
    return T.Compose([
        T.Grayscale(num_output_channels=3),
        T.Resize((img_h, img_w)),
        T.ToTensor(),
        T.Normalize([0.5] * 3, [0.5] * 3),
    ])


class FilteredDataset(Dataset):
    def __init__(self, items: list[dict], vocab: NoteVocab,
                 transform: T.Compose, max_h: int = MAX_H) -> None:
        self._vocab = vocab
        self._transform = transform
        self._items: list[tuple[dict, Path]] = []
        skipped = 0
        for item in items:
            lab = json.loads(Path(item["label_path"]).read_text())
            img_path = Path(lab["image_path"])
            if not img_path.exists():
                skipped += 1
                continue
            if Image.open(img_path).height > max_h:
                skipped += 1
                continue
            self._items.append((lab, img_path))
        log.info("  로드: %d개 (높이>%dpx 필터: %d개)", len(self._items), max_h, skipped)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> dict:
        lab, img_path = self._items[idx]
        img = Image.open(img_path).convert("RGB")
        targets = {}
        for v in VOICE_ORDER:
            notes = [n for m in lab["measures"] for n in m[v]]
            targets[v] = self._vocab.encode(notes)
        return {
            "image": self._transform(img),
            "targets": targets,
            "hymn_id": lab["hymn_id"],
        }


def run_experiment(n_train: int = 50, n_val: int = 10, epochs: int = 10) -> bool:
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    log.info("디바이스: %s", device)

    splits = json.loads(SPLITS_PATH.read_text())
    vocab = NoteVocab()
    transform = _make_transform(IMG_H_EXP, IMG_W_EXP)

    log.info("=== 소규모 실험: n=%d train / %d val / %d epoch / H=%d ===",
             n_train, n_val, epochs, IMG_H_EXP)

    log.info("[train]")
    train_ds = FilteredDataset(splits["train"], vocab, transform)
    train_ds._items = train_ds._items[:n_train]

    log.info("[val]")
    val_ds = FilteredDataset(splits["val"], vocab, transform)
    val_ds._items = val_ds._items[:n_val]

    train_loader = DataLoader(train_ds, batch_size=4, shuffle=True,
                              collate_fn=collate_fn, num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=4, shuffle=False,
                              collate_fn=collate_fn, num_workers=0)

    model = OmrCRNN(vocab.size).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    ctc = nn.CTCLoss(blank=vocab.blank_idx, zero_infinity=True)

    for epoch in range(1, epochs + 1):
        model.train()
        tr_loss = 0.0
        for batch in train_loader:
            images = batch["image"].to(device)
            logits = model(images)
            T_len = logits["S"].size(0)
            inp_len = torch.full((images.size(0),), T_len, dtype=torch.long)
            loss = torch.tensor(0.0, device=device)
            for v in VOICE_ORDER:
                tgt = batch["targets"][v].to(device)
                tgt_len = batch["target_lengths"][v].to(device)
                loss = loss + ctc(logits[v].log_softmax(-1), tgt, inp_len, tgt_len)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            tr_loss += loss.item()

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                logits = model(images)
                T_len = logits["S"].size(0)
                inp_len = torch.full((images.size(0),), T_len, dtype=torch.long)
                loss = torch.tensor(0.0, device=device)
                for v in VOICE_ORDER:
                    tgt = batch["targets"][v].to(device)
                    tgt_len = batch["target_lengths"][v].to(device)
                    loss = loss + ctc(logits[v].log_softmax(-1), tgt, inp_len, tgt_len)
                val_loss += loss.item()

        log.info("Epoch %2d/%d | train=%.4f  val=%.4f",
                 epoch, epochs,
                 tr_loss / max(len(train_loader), 1),
                 val_loss / max(len(val_loader), 1))

    # 추론 샘플 확인
    log.info("\n=== 추론 샘플 (val[0]) ===")
    model.eval()
    lab, img_path = val_ds._items[0]
    x = transform(Image.open(img_path).convert("RGB")).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(x)

    idx2tok = {v: k for k, v in vocab._tok2idx.items()}
    toks = [idx2tok.get(i, "?") for i in logits["S"].argmax(-1)[:, 0].tolist()]
    cnt = Counter(toks)
    log.info("hymn%s S 예측 top-5: %s", lab["hymn_id"], cnt.most_common(5))

    gt = [n["pitch"] for m in lab["measures"] for n in m["S"] if n["pitch"] != "REST"]
    log.info("정답 pitch(앞5): %s", gt[:5])

    pitch_ok = any(
        t not in ("<BLK>", "<EOS>", "REST") and not t.startswith("DUR_") and not t.startswith("TIE_")
        for t in cnt
    )
    log.info("\n결론: %s",
             "✅ pitch 토큰 예측됨 → mode collapse 해소" if pitch_ok
             else "❌ pitch 토큰 없음 → 여전히 mode collapse")
    return pitch_ok


if __name__ == "__main__":
    run_experiment(n_train=50, n_val=10, epochs=10)
