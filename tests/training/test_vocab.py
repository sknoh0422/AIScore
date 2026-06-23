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
