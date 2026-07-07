"""OMR 기준선 평가 — 예측 MusicXML vs GT MusicXML 피치 비교.

사용:
    PYTHONPATH=. python -m training.scripts.eval_baseline \
        --pred training/baseline_eval/homr_out --tag homr

지표:
    - pitch_bag P/R/F1 : 곡 전체 피치 멀티셋 비교 (정렬 불요, 견고한 1차 신호)
    - staff SER        : 보표별 화음 시퀀스 edit distance / len(GT)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path

log = logging.getLogger(__name__)

GT_XML_DIR = Path("score_images/xml/분리")


# ── 지표 함수 (순수, music21 불요) ────────────────────────────────────────────

def edit_distance(a: list[str], b: list[str]) -> int:
    """토큰 시퀀스 Levenshtein 거리."""
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def seq_error_rate(ref: list[str], pred: list[str]) -> float:
    """SER = edit_distance / len(ref). ref가 비어있으면 pred 유무로 0/1."""
    if not ref:
        return 1.0 if pred else 0.0
    return edit_distance(ref, pred) / len(ref)


def pitch_bag_prf(ref: list[str], pred: list[str]) -> tuple[float, float, float]:
    """피치 멀티셋 precision/recall/F1."""
    ref_c, pred_c = Counter(ref), Counter(pred)
    tp = sum((ref_c & pred_c).values())
    if not pred:
        return 0.0, 0.0, 0.0
    p = tp / sum(pred_c.values())
    r = tp / sum(ref_c.values()) if ref else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f


# ── MusicXML → 피치 추출 ─────────────────────────────────────────────────────

def extract_parts(xml_path: Path) -> list[list[list[str]]]:
    """MusicXML → 파트별 화음 시퀀스.

    Returns:
        parts[i] = [chord, ...], chord = 정렬된 피치명 리스트 (쉼표 제외).
    """
    import music21 as m21

    score = m21.converter.parse(str(xml_path))
    parts_out: list[list[list[str]]] = []
    for part in score.parts:
        chords: list[list[str]] = []
        for el in part.flatten().notes:  # notes = Note + Chord (Rest 제외)
            if isinstance(el, m21.chord.Chord):
                chords.append(sorted(p.nameWithOctave for p in el.pitches))
            else:
                chords.append([el.pitch.nameWithOctave])
        parts_out.append(chords)
    return parts_out


def flatten_pitches(parts: list[list[list[str]]]) -> list[str]:
    return [p for part in parts for chord in part for p in chord]


def group_staves(parts: list[list[list[str]]]) -> tuple[list[list[str]], list[list[str]]]:
    """파트들을 (treble, bass) 두 보표 화음 시퀀스로 병합.

    4파트(SATB)면 (S+A, T+B), 2파트면 (0, 1), 1파트면 (0, []).
    같은 시각 두 성부 병합은 인덱스 기준(간이) — SER 하한 추정용.
    """
    def merge(a: list[list[str]], b: list[list[str]]) -> list[list[str]]:
        out = []
        for i in range(max(len(a), len(b))):
            ch = sorted(set((a[i] if i < len(a) else []) + (b[i] if i < len(b) else [])))
            out.append(ch)
        return out

    n = len(parts)
    if n >= 4:
        return merge(parts[0], parts[1]), merge(parts[2], parts[3])
    if n == 3:
        return merge(parts[0], parts[1]), parts[2]
    if n == 2:
        return parts[0], parts[1]
    if n == 1:
        return parts[0], []
    return [], []


def chords_to_tokens(chords: list[list[str]]) -> list[str]:
    return ["+".join(c) for c in chords]


# ── 평가 ─────────────────────────────────────────────────────────────────────

def _hymn_id_from_name(name: str) -> str | None:
    m = re.search(r"hymn(\d+)", name)
    return m.group(1) if m else None


def find_gt_xml(hymn_id: str) -> Path | None:
    matches = sorted(GT_XML_DIR.glob(f"새찬송가_{hymn_id}*.xml"))
    return matches[0] if matches else None


def evaluate_one(pred_xml: Path, gt_xml: Path) -> dict:
    gt_parts = extract_parts(gt_xml)
    pred_parts = extract_parts(pred_xml)

    # 1) 피치 백 P/R/F1
    p, r, f = pitch_bag_prf(flatten_pitches(gt_parts), flatten_pitches(pred_parts))

    # 2) 보표별 SER
    gt_tr, gt_bs = group_staves(gt_parts)
    pr_tr, pr_bs = group_staves(pred_parts)
    ser_tr = seq_error_rate(chords_to_tokens(gt_tr), chords_to_tokens(pr_tr))
    ser_bs = seq_error_rate(chords_to_tokens(gt_bs), chords_to_tokens(pr_bs))

    return {
        "pred": pred_xml.name,
        "gt": gt_xml.name,
        "gt_notes": len(flatten_pitches(gt_parts)),
        "pred_notes": len(flatten_pitches(pred_parts)),
        "bag_precision": round(p, 4),
        "bag_recall": round(r, 4),
        "bag_f1": round(f, 4),
        "ser_treble": round(ser_tr, 4),
        "ser_bass": round(ser_bs, 4),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", type=Path, required=True, help="예측 MusicXML 디렉터리")
    ap.add_argument("--tag", default="baseline", help="결과 파일 태그")
    args = ap.parse_args()

    pred_files = sorted(
        list(args.pred.glob("*.musicxml")) + list(args.pred.glob("*.xml"))
        + list(args.pred.glob("*.mxl"))
    )
    if not pred_files:
        log.error("예측 XML 없음: %s", args.pred)
        return

    results = []
    for pred_xml in pred_files:
        hymn_id = _hymn_id_from_name(pred_xml.name)
        gt_xml = find_gt_xml(hymn_id) if hymn_id else None
        if gt_xml is None:
            log.warning("GT 없음, skip: %s", pred_xml.name)
            continue
        try:
            res = evaluate_one(pred_xml, gt_xml)
        except Exception as e:
            log.warning("평가 실패(%s): %s", pred_xml.name, e)
            continue
        results.append(res)
        log.info(
            "%s  bag P/R/F1=%.2f/%.2f/%.2f  SER tr=%.2f bs=%.2f  (GT %d음 vs 예측 %d음)",
            res["pred"], res["bag_precision"], res["bag_recall"], res["bag_f1"],
            res["ser_treble"], res["ser_bass"], res["gt_notes"], res["pred_notes"],
        )

    if not results:
        log.error("평가된 곡 없음")
        return

    n = len(results)
    summary = {
        "tag": args.tag,
        "n_scores": n,
        "avg_bag_precision": round(sum(r["bag_precision"] for r in results) / n, 4),
        "avg_bag_recall": round(sum(r["bag_recall"] for r in results) / n, 4),
        "avg_bag_f1": round(sum(r["bag_f1"] for r in results) / n, 4),
        "avg_ser_treble": round(sum(r["ser_treble"] for r in results) / n, 4),
        "avg_ser_bass": round(sum(r["ser_bass"] for r in results) / n, 4),
        "results": results,
    }
    out = args.pred / f"eval_{args.tag}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("=== 요약(%d곡): bag F1=%.3f  recall=%.3f  SER tr=%.3f bs=%.3f → %s",
             n, summary["avg_bag_f1"], summary["avg_bag_recall"],
             summary["avg_ser_treble"], summary["avg_ser_bass"], out)


if __name__ == "__main__":
    main()
