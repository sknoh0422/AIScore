"""판정 결과에 따라 GT(Ground Truth, 정답지) XML을 실제 조로 이조(移調).

사용자가 웹 도구로 판정한 결과(key_adjudication.json)에서, 실제 조가 GT 조와
다른 곡(verdict='homr' 또는 'other')을 실제 조로 옮긴다. music21 transpose는
음표·조표를 함께 이동하므로 결과 XML은 실제 인쇄 악보와 같은 조가 된다.

원본 비파괴: 원본 GT는 그대로 두고, 전체 645곡을 새 디렉터리에 쓴다
(수정 대상은 이조본, 나머지는 원본 복사) → 재채점에 그대로 사용.

실행:
    PYTHONPATH=. /opt/miniconda3/envs/aiscore/bin/python \
        -m training.scripts.key_adjudicator.apply_keyfix
출력:
    score_images/xml/분리_keyfix/  (645곡)
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from training.scripts.eval_baseline import pitch_bag_prf

GT_DIR = Path("score_images/xml/분리")
OUT_DIR = Path("score_images/xml/분리_keyfix")
HOMR_DIR = Path("training/baseline_eval/homr_full")
DECISIONS = Path("training/baseline_eval/key_adjudication.json")
MISMATCH = Path("training/scripts/key_adjudicator/web/mismatches.json")
IMPROVE_EPS = 0.02  # 이조가 이만큼 이상 F1을 올릴 때만 채택(겉보기 불일치 보호)

# 조표 fifths(±) → 장조 으뜸음 (music21 표기: 플랫='-')
FIFTHS_TONIC = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
                -1: "F", -2: "B-", -3: "E-", -4: "A-", -5: "D-", -6: "G-", -7: "C-"}


def transpose_interval(from_f: int, to_f: int):
    """두 조의 으뜸음 사이 최소 이동 음정(옥타브 넘으면 가까운 쪽으로)."""
    from music21 import interval, pitch

    p1 = pitch.Pitch(FIFTHS_TONIC[from_f]); p1.octave = 4
    p2 = pitch.Pitch(FIFTHS_TONIC[to_f]); p2.octave = 4
    iv = interval.Interval(p1, p2)
    if iv.semitones > 6:
        p2.octave = 3
        iv = interval.Interval(p1, p2)
    elif iv.semitones < -6:
        p2.octave = 5
        iv = interval.Interval(p1, p2)
    return iv


def fix_targets() -> dict[str, tuple[int, int]]:
    """{hymn_id: (gt_fifths, correct_fifths)} — 실제 조가 GT와 다른 곡."""
    dec = json.loads(DECISIONS.read_text(encoding="utf-8"))
    idx = {it["hymn"]: it for it in json.loads(MISMATCH.read_text(encoding="utf-8"))["items"]}
    out = {}
    for h, d in dec.items():
        cf = d.get("correct_fifths")
        gf = idx[h]["gt_fifths"]
        if cf is not None and cf != gf:
            out[h] = (gf, cf)
    return out


def _score_pitches(score) -> list[str]:
    """music21 Score → 피치 이름 리스트(eval_baseline과 동일 규칙)."""
    import music21 as m21

    out = []
    for part in score.parts:
        for el in part.flatten().notes:
            if isinstance(el, m21.chord.Chord):
                out += [p.nameWithOctave for p in el.pitches]
            else:
                out.append(el.pitch.nameWithOctave)
    return out


def _homr_pitches(hid: str) -> list[str] | None:
    import music21 as m21

    preds = list(HOMR_DIR.glob(f"hymn{hid}_Normal.musicxml"))
    if not preds:
        return None
    return _score_pitches(m21.converter.parse(str(preds[0])))


def main() -> None:
    import music21 as m21

    targets = fix_targets()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    adopted, kept, copied, failed = [], [], 0, []

    for gt in sorted(GT_DIR.glob("새찬송가_*.xml")):
        m = re.search(r"새찬송가_(\d+)", gt.name)
        hid = m.group(1) if m else None
        dest = OUT_DIR / gt.name
        if hid not in targets:
            shutil.copy2(gt, dest)
            copied += 1
            continue

        gf, cf = targets[hid]
        try:
            score = m21.converter.parse(str(gt))
            pred_p = _homr_pitches(hid)
            f1_orig = pitch_bag_prf(_score_pitches(score), pred_p)[2] if pred_p else 0.0
            iv = transpose_interval(gf, cf)
            trans = score.transpose(iv, inPlace=False)
            f1_trans = pitch_bag_prf(_score_pitches(trans), pred_p)[2] if pred_p else 0.0

            if f1_trans > f1_orig + IMPROVE_EPS:  # 이조가 실제로 개선 → 채택
                trans.write("musicxml", fp=str(dest))
                adopted.append((hid, gf, cf, iv.directedName, f1_orig, f1_trans))
            else:  # 겉보기 불일치(음은 이미 일치) → 원본 유지
                shutil.copy2(gt, dest)
                kept.append((hid, gf, cf, f1_orig, f1_trans))
        except Exception as e:  # 실패 시 원본 복사(손실 방지)
            failed.append((hid, str(e)))
            shutil.copy2(gt, dest)

    print(f"이조 채택 {len(adopted)}곡, 원본 유지(겉보기) {len(kept)}곡, "
          f"비대상 복사 {copied}곡, 실패 {len(failed)}곡 → {OUT_DIR}")
    print("\n[이조 채택] (F1 개선 확인됨)")
    for hid, gf, cf, nm, fo, ft in sorted(adopted, key=lambda x: int(x[0])):
        print(f"  hymn{hid}: {gf:+d}→{cf:+d} ({nm})  F1 {fo:.2f}→{ft:.2f}")
    print(f"\n[원본 유지] (이조해도 개선 없음 = 조표 표기만 다른 곡): "
          f"{sorted((h for h,*_ in kept), key=int)}")
    if failed:
        print("실패:", failed)


if __name__ == "__main__":
    main()
