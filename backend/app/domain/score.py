"""내부 Score 도메인 모델 — 순수 Python.

[절대 규칙 B4] 이 모듈은 torch / fastapi / music21 를 import 하지 않는다.
프레임워크·외부 라이브러리와 무관하게 단위 테스트 가능해야 한다.

MusicXML/oemer/music21 의 표현을 이 내부 모델로 변환(파싱 어댑터)한 뒤,
이후 모든 단계(정렬/SVS/믹싱)는 이 모델만 사용한다.

[스텁] 골격만. 필드는 구현 단계에서 확정한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VoiceName(str, Enum):
    SOPRANO = "soprano"
    ALTO = "alto"
    TENOR = "tenor"
    BASS = "bass"


@dataclass
class Note:
    """한 음표. pitch=None 이면 쉼표."""

    pitch: str | None  # 예: "C4", "G#3"; 쉼표는 None
    quarter_length: float  # 4분음표=1.0 기준 길이
    tied: bool = False  # 다음 음표와 붙임줄
    slur: bool = False  # 이음줄(멜리스마) 진행 중
    lyric: str | None = None  # [2단계] 이 음표에 정렬된 음절


@dataclass
class Voice:
    """한 성부의 음표 시퀀스."""

    name: VoiceName
    notes: list[Note] = field(default_factory=list)


@dataclass
class Score:
    """4성부 악보 1곡. SATB 분리 결과."""

    voices: dict[VoiceName, Voice] = field(default_factory=dict)
    title: str | None = None


_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def to_midi(pitch: str) -> int:
    """음이름("C4","G#3","Bb4") → MIDI 번호. A4=69."""
    name = pitch[0].upper()
    i = 1
    semitone = _PC[name]
    while i < len(pitch) and pitch[i] in "#b-":
        semitone += 1 if pitch[i] == "#" else -1
        i += 1
    octave = int(pitch[i:])
    return 12 * (octave + 1) + semitone
