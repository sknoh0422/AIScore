"""Score Understanding 파이프라인 공유 데이터 타입."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BBox:
    """Bounding box representation."""

    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        """Right edge coordinate."""
        return self.x + self.w

    @property
    def y2(self) -> int:
        """Bottom edge coordinate."""
        return self.y + self.h

    @property
    def center_x(self) -> int:
        """Horizontal center coordinate."""
        return self.x + self.w // 2

    @property
    def center_y(self) -> int:
        """Vertical center coordinate."""
        return self.y + self.h // 2


@dataclass
class StaffSystem:
    """Staff system representation."""

    bbox: BBox
    line_ys: list[int]  # 5개 보표선 y좌표 (오름차순, 위→아래)
    clef: str  # "treble" | "bass"

    @property
    def staff_space(self) -> float:
        """보표 한 칸 높이(픽셀). line_ys가 5개여야 한다."""
        return (self.line_ys[-1] - self.line_ys[0]) / 4.0


@dataclass
class LayoutResult:
    """Layout analysis result."""

    image_h: int
    image_w: int
    title_region: BBox | None
    tempo_region: BBox | None
    staff_systems: list[StaffSystem]
    lyric_regions: list[BBox]  # 절 순서대로


@dataclass
class RawDetection:
    """Raw detection result from model."""

    bbox: BBox
    class_name: str  # "notehead_filled", "notehead_open", "accidental_flat", ...
    confidence: float


@dataclass
class NoteEvent:
    """Note event representation."""

    pitch: str  # "C4", "F#5", "Bb3" 등
    duration: float  # quarterLength (1.0=4분, 2.0=2분, 4.0=온음, 0.5=8분)
    voice: int  # 1(S/T) or 2(A/B)
    staff_idx: int  # LayoutResult.staff_systems 인덱스
    x: int  # 음표 x좌표 (악보 내 순서 정렬용)
    measure: int | None = None
    is_dotted: bool = False


@dataclass
class ScoreMeta:
    """Score metadata."""

    title: str = ""
    key: str = "C major"  # "G major", "D minor" 등
    time_num: int = 4
    time_den: int = 4
    tempo_text: str = ""
    bpm: int | None = None


@dataclass
class LyricsResult:
    """Lyrics parsing result."""

    verses: list[list[str]]  # verses[절번호][음표번호] = 음절

    @property
    def verse_count(self) -> int:
        """Number of verses."""
        return len(self.verses)
