from app.domain.score import Note, to_midi


def test_to_midi_a4_is_69():
    assert to_midi("A4") == 69


def test_to_midi_sharp():
    assert to_midi("C#4") == 61


def test_rest_pitch_is_none():
    assert Note(pitch=None, quarter_length=1.0).pitch is None


def test_to_midi_music21_flat():
    assert to_midi("B-4") == 70   # music21 flat notation


def test_to_midi_b_flat_alias():
    assert to_midi("Bb4") == 70
