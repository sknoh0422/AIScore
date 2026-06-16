"""도메인 포트(인터페이스) 정의 — 헥사고날 아키텍처의 경계.

모든 교체 가능한 단계(OMR/가사소스/정렬/SVS/믹싱)는 여기 정의된 Protocol을
구현하는 어댑터로만 연결된다. 오케스트레이터/도메인은 이 추상에만 의존하며
구체 구현(oemer, DiffSinger 등)을 직접 import 하지 않는다.

[중요] 이 파일은 "동결 대상"이다. ports가 확정되기 전에는 stages 구현을
병렬로 시작하지 않는다 (CLAUDE.md 병렬화 원칙 1).

[스텁] 시그니처만 정의. 구현 없음.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .score import Score, VoiceName


@runtime_checkable
class OmrPort(Protocol):
    """L3 OMR: 악보 이미지 → MusicXML(음표). 예) OemerAdapter, AudiverisAdapter."""

    def recognize(self, image_path: Path) -> Path:
        """이미지 경로를 받아 MusicXML 파일 경로를 반환한다."""
        ...


@runtime_checkable
class ScoreParserPort(Protocol):
    """L3 파싱: MusicXML → 내부 Score(SATB 성부 분리). 예) Music21Parser."""

    def parse(self, musicxml_path: Path) -> Score:
        ...


@runtime_checkable
class LyricSourcePort(Protocol):
    """L3 가사 소스 [2단계]: 가사 텍스트 확보. 예) TextInput(기본)/Ocr(보조)."""

    def get_lyrics(self, score: Score) -> Score:
        """절별 가사를 Score에 부착하여 반환한다."""
        ...


@runtime_checkable
class AlignerPort(Protocol):
    """L3 정렬 [2단계]: 음절↔음표 매핑(slur/tie/절 처리)."""

    def align(self, score: Score) -> Score:
        ...


@runtime_checkable
class SvsPort(Protocol):
    """L3 가창 합성: 한 성부 → WAV. 예) VowelSynthAdapter('우')/LyricSingingAdapter."""

    def synthesize(self, score: Score, voice: VoiceName, out_path: Path) -> Path:
        ...


@runtime_checkable
class MixerPort(Protocol):
    """L3 믹싱: 성부별 WAV 목록 → 합창 WAV."""

    def mix(self, voice_wavs: list[Path], out_path: Path) -> Path:
        ...


@runtime_checkable
class CorrectionRecorderPort(Protocol):
    """L4: 교정 (이미지영역, 오답, 정답) 라벨을 데이터셋으로 누적."""

    def record(self, image_region: Path, predicted: str, corrected: str) -> None:
        ...
