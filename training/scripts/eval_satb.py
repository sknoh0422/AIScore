"""Stage C 평가 — homr 4부(SATB) 정확도 실측(성부배정 + 리듬).

기존 eval_baseline.py는 피치 멀티셋(bag) F1만 재어 성부·순서·리듬을 무시한다.
이 스크립트는 **실제 파이프라인이 쓰는 `Music21Parser`**로 GT·homr를 둘 다
SATB Score로 파싱한 뒤 성부(S/A/T/B)별로 대조한다.

지표(성부별):
    - pitch_bag F1 : 그 성부의 피치 멀티셋(순서·리듬 무관) → "성부배정이 맞나"
    - ser_pd       : (pitch@quarter_length) 토큰 시퀀스 SER → "순서+리듬이 맞나"
      · pitch_bag F1(높음)과 ser_pd(낮음)의 격차 = 리듬/순서 오류량

GT: score_images/xml/분리_keyfix (사람이 정정한 조 반영 — 원본 분리/ 아님).
    조 정정본을 써야 GT 조 오류로 homr가 부당하게 깎이지 않는다(key_adjudication.json).

사용:
    PYTHONPATH=backend python -m training.scripts.eval_satb \
        --pred training/baseline_eval/homr_full --tag homr_satb
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

# 실제 서빙 파서 재사용
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.stages.parsing.music21_parser import Music21Parser  # noqa: E402
from app.domain.score import VoiceName  # noqa: E402
from training.scripts.eval_baseline import (  # noqa: E402
    pitch_bag_prf, seq_error_rate,
)

log = logging.getLogger(__name__)

GT_DIR = Path("score_images/xml/분리_keyfix")  # 정정 조 GT
_VOICES = [VoiceName.SOPRANO, VoiceName.ALTO, VoiceName.TENOR, VoiceName.BASS]


def _hymn_id(name: str) -> str | None:
    m = re.search(r"hymn(\d+)", name)
    return m.group(1) if m else None


def _find_gt(hymn_id: str) -> Path | None:
    matches = sorted(GT_DIR.glob(f"새찬송가_{hymn_id}*.xml"))
    return matches[0] if matches else None


def _voice_pitches(notes) -> list[str]:
    """성부의 피치명 리스트(쉼표 제외)."""
    return [n.pitch for n in notes if n.pitch is not None]


def _voice_pd_tokens(notes) -> list[str]:
    """성부의 (pitch@quarter_length) 토큰 — 순서+리듬 포함."""
    return [f"{n.pitch or 'R'}@{n.quarter_length}" for n in notes]


def evaluate_one(pred_xml: Path, gt_xml: Path, parser: Music21Parser) -> dict:
    gt = parser.parse(gt_xml)
    pred = parser.parse(pred_xml)
    per_voice: dict[str, dict] = {}
    for v in _VOICES:
        g = gt.voices.get(v)
        p = pred.voices.get(v)
        if g is None:
            continue  # GT에 없는 성부는 채점 제외
        g_notes = g.notes
        p_notes = p.notes if p is not None else []
        _, _, f1 = pitch_bag_prf(_voice_pitches(g_notes), _voice_pitches(p_notes))
        ser = seq_error_rate(_voice_pd_tokens(g_notes), _voice_pd_tokens(p_notes))
        per_voice[v.value] = {
            "pitch_f1": round(f1, 4),
            "ser_pd": round(ser, 4),
            "gt_notes": len(g_notes),
            "pred_notes": len(p_notes),
        }
    return {"pred": pred_xml.name, "gt": gt_xml.name, "voices": per_voice}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", type=Path, required=True, help="예측 MusicXML 디렉터리")
    ap.add_argument("--tag", default="satb")
    ap.add_argument("--limit", type=int, default=0, help="샘플 N곡만(0=전곡)")
    ap.add_argument("--gt-dir", type=Path, default=None)
    args = ap.parse_args()

    global GT_DIR
    if args.gt_dir is not None:
        GT_DIR = args.gt_dir
    log.info("GT 디렉터리: %s", GT_DIR)

    pred_files = sorted(args.pred.glob("*.musicxml")) + sorted(args.pred.glob("*.xml"))
    if args.limit:
        pred_files = pred_files[: args.limit]
    if not pred_files:
        log.error("예측 XML 없음: %s", args.pred)
        return

    parser = Music21Parser()
    results, failures = [], []
    for pred_xml in pred_files:
        hid = _hymn_id(pred_xml.name)
        gt_xml = _find_gt(hid) if hid else None
        if gt_xml is None:
            continue
        try:
            results.append(evaluate_one(pred_xml, gt_xml, parser))
        except Exception as e:  # 파싱 실패는 조용히 넘기지 않고 집계
            failures.append({"pred": pred_xml.name, "error": str(e)})
            log.warning("실패 %s: %s", pred_xml.name, e)

    # 성부별 매크로 평균
    agg: dict[str, dict] = {}
    for v in _VOICES:
        f1s = [r["voices"][v.value]["pitch_f1"] for r in results if v.value in r["voices"]]
        sers = [r["voices"][v.value]["ser_pd"] for r in results if v.value in r["voices"]]
        if f1s:
            agg[v.value] = {
                "n": len(f1s),
                "avg_pitch_f1": round(sum(f1s) / len(f1s), 4),
                "avg_ser_pd": round(sum(sers) / len(sers), 4),
            }

    summary = {
        "tag": args.tag,
        "n_scored": len(results),
        "n_failed": len(failures),
        "per_voice": agg,
        "results": results,
        "failures": failures,
    }
    out = args.pred.parent / f"eval_satb_{args.tag}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    log.info("채점 %d곡, 실패 %d곡 → %s", len(results), len(failures), out)
    for v, m in agg.items():
        log.info("  %-8s pitch_F1=%.3f  SER(pd)=%.3f  (n=%d)",
                 v, m["avg_pitch_f1"], m["avg_ser_pd"], m["n"])


if __name__ == "__main__":
    main()
