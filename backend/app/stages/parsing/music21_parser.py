"""L3 파싱: MusicXML → 내부 Score, SATB 분리. ScoreParserPort 구현."""
from __future__ import annotations
from pathlib import Path
from music21 import converter, stream, note as m21note
from app.domain.score import Score, Voice, Note, VoiceName

_ORDER = [VoiceName.SOPRANO, VoiceName.ALTO, VoiceName.TENOR, VoiceName.BASS]

class Music21Parser:
    def parse(self, musicxml_path: Path) -> Score:
        parsed = converter.parse(str(musicxml_path))
        parts = list(parsed.getElementsByClass(stream.Part))
        voices: dict[VoiceName, Voice] = {}
        for vn, part in zip(_ORDER, parts):
            notes: list[Note] = []
            for el in part.recurse().notesAndRests:
                ql = float(el.duration.quarterLength)
                if isinstance(el, m21note.Rest):
                    notes.append(Note(pitch=None, quarter_length=ql))
                elif isinstance(el, m21note.Note):
                    notes.append(Note(pitch=el.pitch.nameWithOctave, quarter_length=ql))
                else:  # Chord → 최상단 음 (1단계 단순화)
                    top = max(el.pitches, key=lambda p: p.midi)
                    notes.append(Note(pitch=top.nameWithOctave, quarter_length=ql))
            voices[vn] = Voice(name=vn, notes=notes)
        return Score(voices=voices)
