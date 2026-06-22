# backend/app/stages/omr/musicxml_assembler.py
"""Module 5: music21을 이용한 완전한 MusicXML 조립."""
from __future__ import annotations
from pathlib import Path

import music21
from music21 import stream, note, metadata, tempo, key, meter

from app.stages.omr.types import LyricsResult, NoteEvent, ScoreMeta

_KEY_MAP = {
    "C major": "C", "G major": "G", "D major": "D", "A major": "A",
    "E major": "E", "B major": "B", "F major": "F", "Bb major": "b-",
    "Eb major": "E-", "Ab major": "A-", "F# major": "F#",
    "D minor": "d", "A minor": "a", "E minor": "e", "B minor": "b",
    "G minor": "g", "C minor": "c", "F minor": "f",
}


def assemble(
    meta: ScoreMeta,
    notes: list[NoteEvent],
    lyrics: LyricsResult,
    out_path: Path,
) -> Path:
    """메타정보·음표·가사를 받아 MusicXML 파일로 조립한다."""
    score = stream.Score()

    # 메타데이터
    md = metadata.Metadata()
    md.title = meta.title
    score.insert(0, md)

    # 빠르기
    bpm = meta.bpm or 80
    score.insert(0, tempo.MetronomeMark(number=bpm, referent=note.Note(type="quarter")))

    # 성부별로 음표 분리 (staff_idx 0=트레블, 1=베이스)
    # voice: 1=Soprano or Tenor, 2=Alto or Bass
    voice_map: dict[tuple[int, int], list[NoteEvent]] = {}
    for n in sorted(notes, key=lambda x: x.x):
        k = (n.staff_idx, n.voice)
        voice_map.setdefault(k, []).append(n)

    for (staff_idx, voice), voice_notes in sorted(voice_map.items()):
        part = stream.Part()
        part.id = f"staff{staff_idx}_voice{voice}"

        # 조성기호
        key_str = _KEY_MAP.get(meta.key, "C")
        part.insert(0, key.Key(key_str))
        # 박자기호
        part.insert(0, meter.TimeSignature(f"{meta.time_num}/{meta.time_den}"))

        # 해당 성부 가사 시퀀스
        verse_syllables: list[list[str]] = []
        for verse in lyrics.verses:
            verse_syllables.append(verse[:])

        note_idx = 0
        for evt in voice_notes:
            if evt.pitch.startswith("rest"):
                n_obj = note.Rest(quarterLength=evt.duration)
            else:
                ql = evt.duration * 1.5 if evt.is_dotted else evt.duration
                n_obj = note.Note(evt.pitch, quarterLength=ql)
                # 가사 첨부
                for v_i, syllables in enumerate(verse_syllables, 1):
                    if note_idx < len(syllables):
                        n_obj.addLyric(syllables[note_idx], lyricNumber=v_i)
                note_idx += 1  # Note에만 인덱스 증가 (Rest는 가사 소비 안 함)
            part.append(n_obj)

        score.append(part)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(out_path))
    return out_path
