"""악보 메타정보 추출: 조성·박자·성부·소프라노 계이름."""
from __future__ import annotations
from pathlib import Path
from music21 import converter, key as m21key, meter as m21meter
from music21 import note as m21note, chord as m21chord

_SOLFEGE = {'C': '도', 'D': '레', 'E': '미', 'F': '파', 'G': '솔', 'A': '라', 'B': '시'}
_KEY_MAJOR = {
    0: 'C장조',  1: 'G장조',  2: 'D장조',  3: 'A장조',
    4: 'E장조',  5: 'B장조',  6: 'F#장조', 7: 'C#장조',
   -1: 'F장조', -2: 'Bb장조',-3: 'Eb장조',-4: 'Ab장조',
   -5: 'Db장조',-6: 'Gb장조',-7: 'Cb장조',
}


def _solfege(name: str) -> str:
    """'B-4' → '시b', 'G#5' → '솔#', 'C4' → '도'"""
    base = name[0]
    acc = '#' if len(name) > 1 and name[1] == '#' else ('b' if len(name) > 1 and name[1] == '-' else '')
    return _SOLFEGE.get(base, base) + acc


def extract_meta(musicxml_path: Path) -> dict:
    score = converter.parse(str(musicxml_path))

    # 조성
    keys = list(score.flatten().getElementsByClass(m21key.KeySignature))
    key_name = _KEY_MAJOR.get(keys[0].sharps if keys else 0, '미확인')

    # 박자
    times = list(score.flatten().getElementsByClass(m21meter.TimeSignature))
    time_sig = times[0].ratioString if times else '미확인'

    # 성부 목록
    parts = list(score.parts)
    part_names = [p.partName or p.id or f'Part{i}' for i, p in enumerate(parts)]

    # 소프라노 계이름: Part0 최고음 기준
    soprano: list[dict] = []
    if parts:
        for el in parts[0].flatten().notesAndRests:
            m = getattr(el, 'measureNumber', None)
            if isinstance(el, m21note.Rest):
                soprano.append({'solfege': '쉼', 'pitch': None, 'measure': m})
            elif isinstance(el, m21note.Note):
                soprano.append({'solfege': _solfege(el.nameWithOctave),
                                'pitch': el.nameWithOctave, 'measure': m})
            elif isinstance(el, m21chord.Chord) and el.pitches:
                top = max(el.pitches, key=lambda p: p.midi)
                soprano.append({'solfege': _solfege(top.nameWithOctave),
                                'pitch': top.nameWithOctave, 'measure': m})

    return {
        'key': key_name,
        'time': time_sig,
        'parts': part_names,
        'soprano_notes': soprano,
    }
