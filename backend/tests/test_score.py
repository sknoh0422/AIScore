from app.domain.score import Note, to_midi


def test_to_midi_a4_is_69():
    assert to_midi("A4") == 69


def test_to_midi_sharp():
    assert to_midi("C#4") == 61


def test_rest_pitch_is_none():
    assert Note(pitch=None, quarter_length=1.0).pitch is None
