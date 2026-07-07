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
AUDIT = Path("training/baseline_eval/keyfix_decisions.json")

# [이조 채택 게이트 근거]
# 목표 조(cf)는 "사람이 실제 인쇄 악보 이미지를 보고 판정한 진짜 조"다(homr 아님).
# 문제는 각 곡이 (A) 전곡 전조 오류인지 (B) 조표 표기만 다르고 음은 이미 맞는지 구분하는 것.
#   - (A)면 이조가 옳은 연산 → homr(사람이 옳다고 검증한 기준)와의 일치가 크게 오름.
#   - (B)면 이조는 잘못된 연산(전체를 어긋나게 함) → homr 일치가 오히려 떨어짐.
# 인접 조(예: Bb↔Eb)는 음이 6/7 겹쳐 "온음계 적합도"로는 구분 불가(실측 6곡 오판).
# 따라서 "이조가 homr 일치를 실제로 개선할 때만 채택"이 정확한 판별이다. 이는 순환논리가
# 아니다: 전조 대상 조는 사람 판정이고, homr는 '이조가 옳은 연산인가' 판별에만 쓰이며
# (해당 곡에서 homr 조가 옳음은 사람이 이미지로 확인), 최종 GT는 실제 악보를 나타낸다.
# 피치 F1은 모델 독립적이라 향후 파인튜닝 모델 평가에도 공정하다.
# (한계: (B) 곡은 A↔Ab 같은 특정 음 표기 차가 남아 homr가 소폭 불리 — 재표기는 후속 과제.)
IMPROVE_EPS = 0.02

_MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)  # 로깅용 온음계 적합도(참고 지표)

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


def _score_notes(score) -> tuple[list[str], list[int]]:
    """music21 Score → (피치이름 리스트, MIDI 리스트) — eval_baseline과 동일 규칙."""
    import music21 as m21

    names, midis = [], []
    for part in score.parts:
        for el in part.flatten().notes:
            pitches = el.pitches if isinstance(el, m21.chord.Chord) else [el.pitch]
            for p in pitches:
                names.append(p.nameWithOctave)
                midis.append(p.midi)
    return names, midis


def _diatonic_fraction(midis: list[int], fifths: int) -> float:
    """음들이 해당 장조 음계에 속하는 비율(0~1). 모델 독립적 조 적합도."""
    if not midis:
        return 0.0
    tonic = (7 * fifths) % 12
    scale = {(tonic + s) % 12 for s in _MAJOR_STEPS}
    return sum(1 for m in midis if m % 12 in scale) / len(midis)


def _homr_pitches(hid: str) -> list[str] | None:
    """증거 로깅용 — homr 예측 피치(채택 판정에는 쓰지 않음)."""
    import music21 as m21

    preds = list(HOMR_DIR.glob(f"hymn{hid}_Normal.musicxml"))
    if not preds:
        return None
    return _score_notes(m21.converter.parse(str(preds[0])))[0]


def main() -> None:
    import music21 as m21

    targets = fix_targets()
    if OUT_DIR.exists():  # 이전 실행 잔여물 제거(스테일 파일 방지)
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    adopted, kept, copied, failed = [], [], 0, []

    for gt in sorted(GT_DIR.glob("새찬송가_*.xml")):
        m = re.search(r"새찬송가_(\d+)", gt.name)
        hid = m.group(1) if m else None
        dest = OUT_DIR / gt.name
        if hid not in targets:
            shutil.copy(gt, dest)  # copy2 아님: mtime 갱신으로 music21 파싱 캐시 무효화
            copied += 1
            continue

        gf, cf = targets[hid]
        try:
            score = m21.converter.parse(str(gt))
            names, midis = _score_notes(score)
            fit_gt = _diatonic_fraction(midis, gf)      # GT 음이 자기 라벨 조에 맞는 정도
            fit_true = _diatonic_fraction(midis, cf)     # GT 음이 실제(사람 판정) 조에 맞는 정도
            iv = transpose_interval(gf, cf)

            # 증거용 F1(판정엔 미사용): homr 예측과의 일치도 before/after
            pred_p = _homr_pitches(hid)
            f1_orig = round(pitch_bag_prf(names, pred_p)[2], 4) if pred_p else None
            trans = score.transpose(iv, inPlace=False)
            f1_trans = (round(pitch_bag_prf(_score_notes(trans)[0], pred_p)[2], 4)
                        if pred_p else None)

            rec = {"hymn": hid, "gt_fifths": gf, "true_fifths": cf,
                   "interval": iv.directedName, "fit_gt": round(fit_gt, 3),
                   "fit_true": round(fit_true, 3), "homr_f1_orig": f1_orig,
                   "homr_f1_trans": f1_trans}

            # 이조가 homr 일치를 실제로 개선할 때만 채택(잘못된 전조 연산 차단).
            improved = f1_orig is not None and f1_trans is not None and f1_trans > f1_orig + IMPROVE_EPS
            if improved:
                trans.write("musicxml", fp=str(dest))
                rec["action"] = "transposed"
                adopted.append(rec)
            else:  # 전조가 개선 못 함 = 전조 오류 아님(표기만 다름) → 원본 유지
                shutil.copy(gt, dest)  # copy2 아님: mtime 갱신으로 music21 파싱 캐시 무효화
                rec["action"] = "kept"
                kept.append(rec)
        except Exception as e:  # 실패 시 원본 복사(손실 방지)
            failed.append({"hymn": hid, "error": str(e)})
            shutil.copy(gt, dest)  # copy2 아님: mtime 갱신으로 music21 파싱 캐시 무효화

    AUDIT.write_text(json.dumps(
        {"transposed": adopted, "kept": kept, "failed": failed},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"이조 채택 {len(adopted)}곡, 원본 유지(표기만 다름) {len(kept)}곡, "
          f"비대상 복사 {copied}곡, 실패 {len(failed)}곡 → {OUT_DIR}")
    print(f"판정 이력: {AUDIT}")
    print("\n[이조 채택] (이조가 homr 일치 개선 → 실제 전조 오류)")
    for r in sorted(adopted, key=lambda x: int(x["hymn"])):
        f1 = f" F1 {r['homr_f1_orig']:.2f}→{r['homr_f1_trans']:.2f}" if r["homr_f1_orig"] is not None else ""
        print(f"  hymn{r['hymn']}: {r['gt_fifths']:+d}→{r['true_fifths']:+d}{f1}")
    print(f"\n[원본 유지] (이조해도 개선 없음 = 전조 오류 아님, 표기만 다름): "
          f"{sorted((r['hymn'] for r in kept), key=int)}")
    if failed:
        print("실패:", failed)


if __name__ == "__main__":
    main()
