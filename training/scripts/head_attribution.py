"""Task 2.5 — homr 오류 헤드 귀속(head attribution) 게이트.

목적: homr 플랫 과소인식(피치) 오류가 **어느 디코더 헤드**에서 나오는지 무비용 측정.
    `--fine`(파인튜닝)은 lift 헤드만 학습하므로, 오류가 lift 헤드에 몰려야
    `--fine`이 유효하다. pitch 헤드(보표 위치)면 `--fine`으로 못 고침 → GPU 낭비.

핵심 분해 (homr 최종 발음 피치 = pitch헤드 + lift헤드):
    - staff bag  = {step,octave}         멀티셋 F1  →  **pitch 헤드** 정확도
    - sound bag  = {step,octave,alter}   멀티셋 F1  →  발음 피치(pitch+lift)
    - gap = staff_f1 − sound_f1                     →  **lift 헤드** 기여분(오류량)

판정:
    대상(플랫오류/저F1) 부분집합에서
      staff_f1 ≫ sound_f1  → lift 헤드 지배 → `--fine` GO
      staff_f1 ≈ sound_f1(둘 다 낮음) → pitch 헤드 지배 → `--fine` SKIP(전체 파인튜닝 직행)

GT: score_images/xml/분리_keyfix (정정 조). 조 fifths: 음수=플랫.
homr 플랫 과소인식 = homr_fifths > gt_fifths (플랫을 덜 인식).

사용:
    /opt/miniconda3/envs/aiscore/bin/python -m training.scripts.head_attribution \
        --pred training/baseline_eval/homr_full [--limit N]
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path

import music21

log = logging.getLogger(__name__)

GT_DIR = Path("score_images/xml/분리_keyfix")


def _hymn_id(name: str) -> str | None:
    m = re.search(r"hymn(\d+)", name)
    return m.group(1) if m else None


def _find_gt(hymn_id: str) -> Path | None:
    matches = sorted(GT_DIR.glob(f"새찬송가_{hymn_id}*.xml"))
    return matches[0] if matches else None


def _bags_and_key(xml_path: Path) -> tuple[list[str], list[str], int | None]:
    """(staff_bag, sound_bag, fifths) 추출.

    staff = step+octave (임시표 무시, pitch 헤드), sound = step+octave+alter.
    """
    score = music21.converter.parse(str(xml_path))
    staff: list[str] = []
    sound: list[str] = []
    for n in score.recurse().notes:  # Note + Chord
        pitches = n.pitches if n.isChord else [n.pitch]
        for p in pitches:
            staff.append(f"{p.step}{p.octave}")
            alter = int(p.alter) if p.alter == int(p.alter) else p.alter
            sound.append(f"{p.step}{p.octave}{alter:+d}")
    fifths = None
    ks = score.recurse().getElementsByClass(music21.key.KeySignature)
    if ks:
        fifths = int(ks[0].sharps)  # 음수=플랫
    return staff, sound, fifths


def _bag_f1(pred: list[str], gt: list[str]) -> float:
    if not pred and not gt:
        return 1.0
    if not pred or not gt:
        return 0.0
    tp = sum((Counter(pred) & Counter(gt)).values())
    prec = tp / len(pred)
    rec = tp / len(gt)
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


def evaluate_one(pred_xml: Path, gt_xml: Path) -> dict:
    p_staff, p_sound, p_fifths = _bags_and_key(pred_xml)
    g_staff, g_sound, g_fifths = _bags_and_key(gt_xml)
    staff_f1 = _bag_f1(p_staff, g_staff)
    sound_f1 = _bag_f1(p_sound, g_sound)
    return {
        "pred": pred_xml.name,
        "gt": gt_xml.name,
        "staff_f1": round(staff_f1, 4),   # pitch 헤드
        "sound_f1": round(sound_f1, 4),   # pitch+lift
        "lift_gap": round(staff_f1 - sound_f1, 4),  # lift 헤드 기여
        "gt_fifths": g_fifths,
        "homr_fifths": p_fifths,
        # 플랫 과소인식: GT가 플랫이 더 많음(더 음수) → homr가 덜 인식
        "flat_deficit": (
            None if g_fifths is None or p_fifths is None
            else max(0, p_fifths - g_fifths)
        ),
        "n_gt": len(g_sound),
        "n_pred": len(p_sound),
    }


def _agg(rows: list[dict], label: str) -> dict:
    if not rows:
        return {"label": label, "n": 0}
    n = len(rows)
    return {
        "label": label,
        "n": n,
        "avg_staff_f1": round(sum(r["staff_f1"] for r in rows) / n, 4),
        "avg_sound_f1": round(sum(r["sound_f1"] for r in rows) / n, 4),
        "avg_lift_gap": round(sum(r["lift_gap"] for r in rows) / n, 4),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--gt-dir", type=Path, default=None)
    args = ap.parse_args()

    global GT_DIR
    if args.gt_dir is not None:
        GT_DIR = args.gt_dir

    pred_files = sorted(args.pred.glob("*.musicxml")) + sorted(args.pred.glob("*.xml"))
    if args.limit:
        pred_files = pred_files[: args.limit]
    if not pred_files:
        log.error("예측 XML 없음: %s", args.pred)
        return

    results, failures = [], []
    for i, pred_xml in enumerate(pred_files, 1):
        hid = _hymn_id(pred_xml.name)
        gt_xml = _find_gt(hid) if hid else None
        if gt_xml is None:
            continue
        try:
            results.append(evaluate_one(pred_xml, gt_xml))
        except Exception as e:
            failures.append({"pred": pred_xml.name, "error": str(e)})
            log.warning("실패 %s: %s", pred_xml.name, e)
        if i % 50 == 0:
            log.info("... %d/%d", i, len(pred_files))

    # 슬라이스
    all_rows = results
    flat_err = [r for r in results if r["flat_deficit"]]  # >0
    # 저 발음-F1 하위 25%
    thr = sorted(r["sound_f1"] for r in results)[max(0, len(results) // 4 - 1)] if results else 0
    low_f1 = [r for r in results if r["sound_f1"] <= thr]

    aggs = [
        _agg(all_rows, "ALL"),
        _agg(flat_err, "FLAT_UNDER (homr fifths > gt fifths)"),
        _agg(low_f1, f"LOW_SOUND_F1 (<= {thr:.3f}, 하위25%)"),
    ]

    summary = {
        "n_scored": len(results),
        "n_failed": len(failures),
        "aggregates": aggs,
        "results": results,
        "failures": failures,
    }
    out = args.pred.parent / "head_attribution.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    log.info("채점 %d곡, 실패 %d곡 → %s", len(results), len(failures), out)
    log.info("=" * 64)
    for a in aggs:
        if a["n"]:
            log.info("[%s] n=%d  staff_F1(pitch헤드)=%.3f  sound_F1(pitch+lift)=%.3f  lift_gap=%.3f",
                     a["label"], a["n"], a["avg_staff_f1"], a["avg_sound_f1"], a["avg_lift_gap"])


if __name__ == "__main__":
    main()
