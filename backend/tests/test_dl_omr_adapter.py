"""DlOmrAdapter 단위 테스트 — TDD Step 1."""
from __future__ import annotations

from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock


def test_dl_omr_adapter_implements_omr_port():
    """DlOmrAdapter 가 OmrPort Protocol 을 충족하는지 확인 (model_path=None 허용)."""
    from app.stages.omr.dl_omr_adapter import DlOmrAdapter
    from app.domain.ports import OmrPort

    adapter = DlOmrAdapter(work_dir=Path("/tmp"), model_path=None)
    assert isinstance(adapter, OmrPort)


def test_dl_omr_adapter_no_model_raises(tmp_path):
    """모델 가중치 없이 recognize() 호출하면 RuntimeError 발생."""
    from app.stages.omr.dl_omr_adapter import DlOmrAdapter

    adapter = DlOmrAdapter(work_dir=tmp_path, model_path=None)
    dummy_img = tmp_path / "test.png"
    dummy_img.write_bytes(b"")
    with pytest.raises(RuntimeError, match="모델 가중치"):
        adapter.recognize(dummy_img)


def test_note_vocab_size():
    """NoteVocab vocab 크기가 train_omr.py 와 동일한지 확인."""
    from app.stages.omr.dl_omr_adapter import _NoteVocab

    vocab = _NoteVocab()
    # specials(4) + pitches(1 REST + 5 octaves × 7 steps × 3 accidentals = 105 + 1 = 106) + durations(9) = 119
    assert vocab.size == 119


def test_note_vocab_blank_idx():
    """blank_idx 가 0 이어야 한다 (CTC 요구)."""
    from app.stages.omr.dl_omr_adapter import _NoteVocab

    vocab = _NoteVocab()
    assert vocab.blank_idx == 0


def test_note_vocab_decode_empty():
    """blank 인덱스만 있으면 빈 리스트를 반환해야 한다."""
    from app.stages.omr.dl_omr_adapter import _NoteVocab

    vocab = _NoteVocab()
    result = vocab.decode([vocab.blank_idx, vocab.blank_idx])
    assert result == []


def test_note_vocab_decode_pitch_duration():
    """pitch + duration 토큰 디코딩이 올바른 음표 dict 를 반환해야 한다."""
    from app.stages.omr.dl_omr_adapter import _NoteVocab

    vocab = _NoteVocab()
    # "C4" pitch 와 "DUR_1.0" duration 인코딩하여 디코딩 확인
    tok2idx = vocab._tok2idx
    indices = [tok2idx["C4"], tok2idx["DUR_1.0"]]
    notes = vocab.decode(indices)
    assert len(notes) == 1
    assert notes[0]["pitch"] == "C4"
    assert notes[0]["duration"] == 1.0


def test_dl_omr_adapter_model_path_missing_logs_warning(tmp_path):
    """존재하지 않는 model_path 를 전달하면 경고만 로그하고 RuntimeError 는 raise 하지 않는다."""
    from app.stages.omr.dl_omr_adapter import DlOmrAdapter

    missing = tmp_path / "nonexistent.pt"
    # 생성자에서 RuntimeError 가 나면 안 됨
    adapter = DlOmrAdapter(work_dir=tmp_path, model_path=missing)
    assert adapter._model is None
