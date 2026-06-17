"""L3 파싱: MusicXML → 내부 Score. part×voice를 S/A/T/B에 있는 만큼 매핑."""
from __future__ import annotations
from pathlib import Path
from music21 import converter, stream, note as m21note
from app.core.errors import ParseError
from app.domain.score import Score, Voice, Note, VoiceName

_ORDER = [VoiceName.SOPRANO, VoiceName.ALTO, VoiceName.TENOR, VoiceName.BASS]

def _notes_from(elements) -> list[Note]:
    out: list[Note] = []
    for el in elements:
        if isinstance(el, m21note.Rest):
            out.append(Note(pitch=None, quarter_length=float(el.duration.quarterLength)))
        elif isinstance(el, m21note.Note):
            out.append(Note(pitch=el.pitch.nameWithOctave,
                            quarter_length=float(el.duration.quarterLength)))
        elif hasattr(el, "pitches") and el.pitches:  # Chord → 최상단
            top = max(el.pitches, key=lambda p: p.midi)
            out.append(Note(pitch=top.nameWithOctave,
                            quarter_length=float(el.duration.quarterLength)))
    return out

class Music21Parser:
    def parse(self, musicxml_path: Path) -> Score:
        parsed = converter.parse(str(musicxml_path))
        lines: list[list[Note]] = []
        for part in parsed.getElementsByClass(stream.Part):
            ns = _notes_from(part.recurse().notesAndRests)
            if ns:
                lines.append(ns)
        if not lines:
            raise ParseError(f"파싱 결과 음표 없음: {musicxml_path}")
        voices_map: dict[VoiceName, Voice] = {}
        for vn, notes in zip(_ORDER, lines):
            voices_map[vn] = Voice(name=vn, notes=notes)
        return Score(voices=voices_map)
