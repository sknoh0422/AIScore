"""StaffCRNN 아키텍처 단위 테스트."""
from __future__ import annotations

import torch
import pytest

from training.scripts.train_omr import StaffCRNN, NoteVocab, STAFF_IMG_H, STAFF_IMG_W


@pytest.fixture
def vocab():
    return NoteVocab()


def _dummy_batch(B: int = 2, H: int = STAFF_IMG_H, W: int = STAFF_IMG_W) -> torch.Tensor:
    torch.manual_seed(0)
    return torch.rand(B, 3, H, W)


def _ctc_greedy(logits_T_B_V: torch.Tensor, blank_idx: int) -> list[int]:
    """(T, B=1, V) → CTC greedy: 중복 제거 + BLK 제거."""
    ids = logits_T_B_V.argmax(-1)[:, 0].tolist()
    out, prev = [], None
    for i in ids:
        if i != prev:
            if i != blank_idx:
                out.append(i)
        prev = i
    return out


# ── 출력 shape ──────────────────────────────────────────────────────────────

def test_staff_crnn_treble_output_voices(vocab):
    model = StaffCRNN(vocab.size, "treble")
    model.eval()
    with torch.no_grad():
        logits = model(_dummy_batch())
    assert set(logits.keys()) == {"S", "A"}


def test_staff_crnn_bass_output_voices(vocab):
    model = StaffCRNN(vocab.size, "bass")
    model.eval()
    with torch.no_grad():
        logits = model(_dummy_batch())
    assert set(logits.keys()) == {"T", "B"}


def test_staff_crnn_logit_vocab_size(vocab):
    model = StaffCRNN(vocab.size, "treble")
    model.eval()
    with torch.no_grad():
        logits = model(_dummy_batch(B=2))
    T, B, V = logits["S"].shape
    assert V == vocab.size
    assert B == 2
    assert T > 0


def test_staff_crnn_time_axis_gt_1(vocab):
    """T > 1 이어야 CTC가 동작."""
    model = StaffCRNN(vocab.size, "treble")
    model.eval()
    with torch.no_grad():
        logits = model(_dummy_batch(B=1))
    T = logits["S"].size(0)
    assert T > 1


# ── 높이 보존 확인 ──────────────────────────────────────────────────────────

def test_staff_crnn_height_gt_1_before_flatten(vocab):
    """encoder 출력 H' > 1 (pitch 정보 보존 확인)."""
    model = StaffCRNN(vocab.size, "treble")
    model.eval()

    captured = {}
    def _hook(module, inp, out):
        captured["h_prime"] = out.shape[2]

    model.channel_reduce.register_forward_hook(_hook)
    with torch.no_grad():
        model(_dummy_batch(B=1))
    assert captured["h_prime"] > 1, f"H' = {captured.get('h_prime')} (pool_h 버그 재발 가능성)"


# ── 오버핏 테스트 (단일 샘플) ────────────────────────────────────────────────

def test_staff_crnn_can_overfit_single_sample(vocab):
    """단일 샘플 50 에포크 과적합 → CTC greedy decode에 pitch 토큰 ≥1 개."""
    device = torch.device("cpu")
    model  = StaffCRNN(vocab.size, "treble").to(device)
    opt    = torch.optim.Adam(model.parameters(), lr=1e-3)
    ctc    = torch.nn.CTCLoss(blank=vocab.blank_idx, zero_infinity=True)

    # W=400 → T=25: 빠른 실행 + CTC 조건(T>=11) 충족
    torch.manual_seed(42)
    x = torch.rand(1, 3, STAFF_IMG_H, 400).to(device)

    target_seq = torch.tensor(
        vocab.encode([
            {"pitch": "C4", "duration": 1.0, "tie_start": False, "tie_end": False},
            {"pitch": "E4", "duration": 1.0, "tie_start": False, "tie_end": False},
            {"pitch": "G4", "duration": 1.0, "tie_start": False, "tie_end": False},
        ]),
        dtype=torch.long,
    ).unsqueeze(0)  # (1, L=6)
    tgt_len = torch.tensor([target_seq.size(1)])

    for _ in range(50):
        model.train()
        logits = model(x)
        T_len = logits["S"].size(0)
        inp_len = torch.tensor([T_len])
        loss = ctc(logits["S"].log_softmax(-1), target_seq, inp_len, tgt_len)
        opt.zero_grad()
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        logits = model(x)

    decoded = _ctc_greedy(logits["S"], vocab.blank_idx)
    idx2tok = {v: k for k, v in vocab._tok2idx.items()}
    tokens  = [idx2tok.get(i, "?") for i in decoded]
    pitch_tokens = [
        t for t in tokens
        if t not in ("<BLK>", "<EOS>", "REST")
        and not t.startswith("DUR_")
        and not t.startswith("TIE_")
    ]
    assert len(pitch_tokens) >= 1, f"pitch 토큰 없음 (mode collapse). 디코딩: {tokens}"
