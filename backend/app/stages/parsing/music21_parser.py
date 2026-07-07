"""L3 파싱: MusicXML → 내부 Score.

Audiveris 출력 구조:
  - Grand staff 2-Part: Part0(G clef)=S+A 화음, Part1(F clef)=T+B 화음
  - 화음 상단 → 위 성부(S/T), 하단 → 아래 성부(A/B) 로 분리
homr 출력 구조:
  - 단일 "Piano" 파트가 music21에서 2개 PartStaff(treble/bass)로 파싱됨.
  - 파트명이 "Piano"라 악기 필터에 걸리므로, 필터 결과가 0줄이면 필터를 해제(폴백).

악기 필터: 파트명에 악기 키워드(Piano, Organ 등)가 있으면 제외.
파트명 없으면 성악으로 간주(폴백).
"""
from __future__ import annotations
import logging
from pathlib import Path
from music21 import converter, stream, note as m21note
from app.core.errors import ParseError
from app.domain.score import Score, Voice, Note, VoiceName

_logger = logging.getLogger(__name__)

_ORDER = [VoiceName.SOPRANO, VoiceName.ALTO, VoiceName.TENOR, VoiceName.BASS]

_INSTRUMENT_KEYWORDS = {
    "piano", "organ", "guitar", "keyboard", "accomp",
    "strings", "orch", "instr", "drum", "perc", "bass guitar",
    "피아노", "오르간", "기타", "건반", "반주",
}


def _is_vocal_part(part) -> bool:
    """파트명 기반 성악 여부 판별. 파트명 없으면 성악으로 간주."""
    name = (part.partName or "").lower().strip()
    if not name:
        return True
    return not any(k in name for k in _INSTRUMENT_KEYWORDS)


def _split_two_voices(elements) -> tuple[list[Note], list[Note]]:
    """화음(chord)에서 상단·하단 성부를 분리한다.
    단음은 두 성부에 동일하게 배치. 쉼표도 양쪽에 배치."""
    upper: list[Note] = []
    lower: list[Note] = []
    for el in elements:
        dur = float(el.duration.quarterLength)
        if isinstance(el, m21note.Rest):
            upper.append(Note(pitch=None, quarter_length=dur))
            lower.append(Note(pitch=None, quarter_length=dur))
        elif isinstance(el, m21note.Note):
            upper.append(Note(pitch=el.pitch.nameWithOctave, quarter_length=dur))
            lower.append(Note(pitch=el.pitch.nameWithOctave, quarter_length=dur))
        elif hasattr(el, "pitches") and el.pitches:
            by_midi = sorted(el.pitches, key=lambda p: p.midi)
            if len(by_midi) > 2:
                # 3+ 피치 코드: 상단/하단만 취하고 중간 음 제거 (의도적)
                _logger.warning("3+ 피치 코드 %d개 → 상/하단만 사용, 중간음 %d개 제거",
                                len(by_midi), len(by_midi) - 2)
            top = by_midi[-1].nameWithOctave
            bot = by_midi[0].nameWithOctave
            upper.append(Note(pitch=top, quarter_length=dur))
            lower.append(Note(pitch=bot, quarter_length=dur))
    return upper, lower


class Music21Parser:
    def parse(self, musicxml_path: Path) -> Score:
        parsed = converter.parse(str(musicxml_path))
        parts = list(parsed.getElementsByClass(stream.Part))

        # 1차: 악기 파트 제외(Audiveris 반주 배제용)
        lines = self._extract_lines(parts, vocal_only=True)
        if not lines:
            # 모든 파트가 악기명이지만 실제 성악 내용인 경우
            # (homr는 항상 파트명을 "Piano"로 내보냄) → 필터 해제 재추출
            _logger.info("성악 파트 필터 결과 0줄 → 악기 필터 해제 폴백")
            lines = self._extract_lines(parts, vocal_only=False)

        if not lines:
            raise ParseError(f"파싱 결과 음표 없음: {musicxml_path}")

        voices_map: dict[VoiceName, Voice] = {}
        for vn, notes in zip(_ORDER, lines):
            voices_map[vn] = Voice(name=vn, notes=notes)
        return Score(voices=voices_map)

    def _extract_lines(self, parts, vocal_only: bool) -> list[list[Note]]:
        lines: list[list[Note]] = []
        for part in parts:
            if vocal_only and not _is_vocal_part(part):
                continue
            elements = list(part.recurse().notesAndRests)
            has_chord = any(hasattr(e, "pitches") and len(e.pitches) >= 2
                            for e in elements)
            if has_chord:
                upper, lower = _split_two_voices(elements)
                if upper:
                    lines.append(upper)
                if lower:
                    lines.append(lower)
            else:
                ns: list[Note] = []
                for el in elements:
                    dur = float(el.duration.quarterLength)
                    if isinstance(el, m21note.Rest):
                        ns.append(Note(pitch=None, quarter_length=dur))
                    elif isinstance(el, m21note.Note):
                        ns.append(Note(pitch=el.pitch.nameWithOctave,
                                       quarter_length=dur))
                if ns:
                    lines.append(ns)
        return lines
