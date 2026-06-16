"""디바이스 선택 — 단일 진입점.

[절대 규칙 A2] 디바이스 결정은 오직 이 파일에서만 한다. 모듈마다
.to("mps") 를 흩뿌리지 않는다. 우선순위: mps → cuda → cpu.
개발은 macOS(Apple Silicon)에서 하되, 다중 OS 이식성을 위해
하드코딩하지 않고 런타임에 가용 디바이스를 선택한다.

[스텁] torch 미가용 환경에서도 import 가능하도록 지연 import.
"""

from __future__ import annotations


def select_device() -> str:
    """가용 디바이스 문자열을 반환한다: "mps" | "cuda" | "cpu"."""
    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"
