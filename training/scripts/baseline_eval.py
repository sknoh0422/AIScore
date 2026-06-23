"""Audiveris 기준선 정확도 측정 — val set 20개.

Audiveris 바이너리가 없을 경우: 이전 실측치(315.JPG ≈65%)를 근거로
"Audiveris 없음 — 예상 정확도 ≈65%" 메시지를 출력하고 None 반환.
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

import music21 as m21

log = logging.getLogger(__name__)

SPLITS = Path("training/data/splits.json")
LABELS = Path("training/data/labels")
AUDIVERIS = Path("vendor/audiveris/bin/Audiveris")
JDK25 = "/opt/homebrew/opt/openjdk@25/bin/java"
SAMPLE_SIZE = 20

# 이전 수동 측정치 (315.JPG 단일 샘플)
PRIOR_ACCURACY = 0.65


def run_audiveris(image_path: Path, out_dir: Path) -> Path | None:
    """Audiveris를 실행하고 MXL 파일 경로를 반환.

    바이너리가 없거나 실행 실패 시 None 반환.
    """
    if not AUDIVERIS.exists():
        log.warning("Audiveris 바이너리 없음: %s", AUDIVERIS)
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        JDK25, "-jar", str(AUDIVERIS),
        "-batch", "-transcribe", "-export",
        "-output", str(out_dir), str(image_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            log.warning(
                "Audiveris 종료코드 %d: %s",
                result.returncode,
                result.stderr.decode(errors="replace")[:200],
            )
    except subprocess.TimeoutExpired:
        log.warning("Audiveris 타임아웃: %s", image_path)
        return None
    mxl = next(out_dir.glob("**/*.mxl"), None)
    return mxl


def pitch_accuracy(pred_notes: list[str], gt_notes: list[str]) -> float:
    """위치 정렬 기반 음표 정확도 (0.0 – 1.0)."""
    if not gt_notes:
        return 1.0
    correct = sum(p == g for p, g in zip(pred_notes, gt_notes))
    return correct / max(len(pred_notes), len(gt_notes))


def extract_soprano_pitches(mxl_path: Path) -> list[str]:
    """MXL 첫 번째 파트(소프라노)에서 음표 피치 리스트 추출."""
    try:
        score = m21.converter.parse(str(mxl_path))
        if not score.parts:
            return []
        part = score.parts[0]
        return [
            n.pitch.nameWithOctave
            for n in part.flatten().notes
            if isinstance(n, m21.note.Note)
        ]
    except Exception as e:
        log.warning("MXL 파싱 실패 %s: %s", mxl_path, e)
        return []


def evaluate() -> float | None:
    """val set SAMPLE_SIZE 개로 Audiveris 기준선 정확도 측정.

    Returns
    -------
    float | None
        측정된 평균 소프라노 음표 정확도. Audiveris 없으면 None.
    """
    if not SPLITS.exists():
        print(f"[오류] splits.json 없음: {SPLITS}")
        return None

    splits = json.loads(SPLITS.read_text())
    val_items = splits["val"][:SAMPLE_SIZE]

    if not AUDIVERIS.exists():
        print("=" * 55)
        print("Audiveris 바이너리 없음.")
        print(f"  기대 경로: {AUDIVERIS.resolve()}")
        print()
        print("이전 실측치 (315.JPG 단일 샘플) 기반 추정:")
        print(f"  예상 소프라노 음표 정확도: {PRIOR_ACCURACY:.1%}")
        print()
        print("결론: 자체 학습 진행 (예상 정확도 < 95%)")
        print("=" * 55)
        print()
        print("실제 측정 방법:")
        print("  1. vendor/audiveris/bin/Audiveris 설치")
        print("  2. python training/scripts/baseline_eval.py 재실행")
        return None

    accuracies: list[float] = []
    with tempfile.TemporaryDirectory() as tmp:
        for item in val_items:
            label_file = LABELS / f"hymn{item['hymn_id']}.json"
            if not label_file.exists():
                log.warning("라벨 없음: %s", label_file)
                continue

            label = json.loads(label_file.read_text())
            image_path = Path(label["image_path"])

            gt_notes = [
                n["pitch"]
                for m in label["measures"]
                for n in m["S"]
                if n["pitch"] != "REST"
            ]

            mxl = run_audiveris(image_path, Path(tmp) / item["hymn_id"])
            if mxl is None:
                log.warning("Audiveris 실패: hymn%s", item["hymn_id"])
                accuracies.append(0.0)
                continue

            pred_notes = extract_soprano_pitches(mxl)
            acc = pitch_accuracy(pred_notes, gt_notes)
            accuracies.append(acc)
            log.info(
                "hymn%s: GT=%d, Pred=%d, acc=%.1f%%",
                item["hymn_id"], len(gt_notes), len(pred_notes), acc * 100,
            )

    if not accuracies:
        print("[경고] 평가 샘플이 없습니다.")
        return None

    mean_acc = sum(accuracies) / len(accuracies)
    print(f"\n=== Audiveris 기준선 정확도 (n={len(accuracies)}) ===")
    print(f"평균 소프라노 음표 정확도: {mean_acc:.1%}")
    print("결론:", "자체 학습 진행" if mean_acc < 0.95 else "Audiveris 충분 — 재검토 필요")
    return mean_acc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    evaluate()
