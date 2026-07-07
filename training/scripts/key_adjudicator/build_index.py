"""조표(調標, key signature) 불일치 서브 인덱스 생성.

homr(사전학습 OMR) 예측과 GT(Ground Truth, 정답지) XML의 기본 조표가 다른 곡만
추출해 항목 배열(서브 인덱스)로 저장한다. 웹 판정 도구가 이 인덱스만 읽는다.

실행:
    PYTHONPATH=. /opt/miniconda3/envs/aiscore/bin/python \
        -m training.scripts.key_adjudicator.build_index
출력:
    training/scripts/key_adjudicator/web/mismatches.json
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter
from pathlib import Path

HOMR_DIR = Path("training/baseline_eval/homr_full")
GT_DIR = Path("score_images/xml/분리")
SHIFT_JSON = HOMR_DIR / "shift_analysis.json"
OUT = Path("training/scripts/key_adjudicator/web/mismatches.json")

# 조표 fifths(±) → 장조 으뜸음 이름
NAMES = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
         -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb"}


def key_name(f: int) -> str:
    return f"{NAMES.get(f, '?')}장조"


def first_fifths(path: Path) -> int | None:
    """파일 내 조표들의 최빈 fifths 값. 조표 없으면 None."""
    import music21 as m21

    score = m21.converter.parse(str(path))
    ks = list(score.recurse().getElementsByClass(m21.key.KeySignature))
    if not ks:
        return None
    return Counter(k.sharps for k in ks).most_common(1)[0][0]


def gt_for(hymn_id: str) -> Path | None:
    matches = sorted(GT_DIR.glob(f"새찬송가_{hymn_id}*.xml"))
    return matches[0] if matches else None


def title_of(gt: Path, hymn_id: str) -> str:
    """'새찬송가_480 천국에서 만나 보자' → '천국에서 만나 보자'."""
    return re.sub(rf"^새찬송가_{hymn_id}\s*", "", gt.stem) or gt.stem


def build() -> dict:
    shift = {}
    if SHIFT_JSON.exists():
        shift = {x["hymn"]: x for x in json.loads(SHIFT_JSON.read_text(encoding="utf-8"))}

    items = []
    for pred in sorted(HOMR_DIR.glob("hymn*_Normal.musicxml")):
        hymn_id = re.search(r"hymn(\d+)", pred.name).group(1)
        gt = gt_for(hymn_id)
        if gt is None:
            continue
        try:
            hf, gf = first_fifths(pred), first_fifths(gt)
        except Exception:
            continue
        if hf is None or gf is None or hf == gf:
            continue
        sh = shift.get(hymn_id, {})
        items.append({
            "hymn": hymn_id,
            "title": title_of(gt, hymn_id),
            "homr_fifths": hf, "homr_key": key_name(hf),
            "gt_fifths": gf, "gt_key": key_name(gf),
            "base_f1": sh.get("base_f1"),
            "shift": sh.get("shift"),
            "img": f"{pred.stem}.png",
        })
    items.sort(key=lambda x: int(x["hymn"]))
    return {"count": len(items), "items": items}


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"조표 불일치 {data['count']}곡 → {OUT}")


if __name__ == "__main__":
    main()
