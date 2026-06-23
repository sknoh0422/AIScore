"""XML→JSON 라벨 추출 + 시스템 단위 크롭 + train/val/test 분할."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import music21 as m21
from sklearn.model_selection import train_test_split

from training.scripts.crop_staves import find_system_boundaries, crop_system

log = logging.getLogger(__name__)

PNG_DIR = Path("score_images/png")
XML_DIR = Path("score_images/xml/분리")
OUT_DIR = Path("training/data")

VOICE_ORDER = ("S", "A", "T", "B")  # Part 0~3 순서


def _hymn_num_from_xml(xml_path: Path) -> str:
    """새찬송가_001 ... → '001'"""
    m = re.match(r"새찬송가_(\d+)", xml_path.stem)
    if not m:
        raise ValueError(f"XML 파일명 패턴 불일치: {xml_path.name}")
    return m.group(1)


def _note_to_dict(n: m21.note.GeneralNote) -> dict:
    if isinstance(n, m21.note.Rest):
        return {
            "pitch": "REST",
            "duration": float(n.duration.quarterLength),
            "tie_start": False,
            "tie_end": False,
        }
    if isinstance(n, m21.chord.Chord):
        # 코드(화음)는 최저음을 대표음으로 사용
        n = n.sortAscending().notes[0]
    pitch_str = n.pitch.nameWithOctave  # e.g., "A-4"
    tie_start = n.tie is not None and n.tie.type in ("start", "continue")
    tie_end = n.tie is not None and n.tie.type in ("stop", "continue")
    return {
        "pitch": pitch_str,
        "duration": float(n.duration.quarterLength),
        "tie_start": tie_start,
        "tie_end": tie_end,
    }


def parse_xml(xml_path: Path) -> dict:
    """MusicXML → 라벨 dict. measures 리스트는 measure_num 기준 정렬."""
    hymn_id = _hymn_num_from_xml(xml_path)
    png_name = f"hymn{hymn_id}_Normal.png"

    score = m21.converter.parse(str(xml_path))
    parts = score.parts
    if len(parts) < 4:
        raise ValueError(f"{xml_path.name}: 파트 수 {len(parts)} < 4")

    # 박자표 / 조표
    ts = score.flatten().getElementsByClass("TimeSignature")
    ks = score.flatten().getElementsByClass("KeySignature")
    ts_obj = list(ts)[0] if ts else None
    time_sig = ts_obj.ratioString if ts_obj else "4/4"
    key_sig = list(ks)[0].sharps if ks else 0

    # 성부별 마디 → 음표 추출
    measures_by_num: dict[int, dict] = {}
    for voice_idx, voice_name in enumerate(VOICE_ORDER):
        part = parts[voice_idx]
        for measure in part.getElementsByClass("Measure"):
            mnum = measure.number
            if mnum not in measures_by_num:
                measures_by_num[mnum] = {"measure_num": mnum, "S": [], "A": [], "T": [], "B": []}
            notes = [_note_to_dict(n) for n in measure.flatten().notesAndRests]
            measures_by_num[mnum][voice_name] = notes

    measures = sorted(measures_by_num.values(), key=lambda x: x["measure_num"])
    # measure_num=0 (전주 쉼표 마디) 제거
    measures = [m for m in measures if m["measure_num"] > 0]

    return {
        "hymn_id": hymn_id,
        "image_path": str(PNG_DIR / png_name),
        "time_signature": time_sig,
        "key_signature": key_sig,
        "measures": measures,
    }


def split_dataset(items: list[dict], seed: int = 42) -> dict[str, list[dict]]:
    """80/10/10 train/val/test 분할."""
    train_val, test = train_test_split(items, test_size=0.1, random_state=seed)
    train, val = train_test_split(train_val, test_size=0.111, random_state=seed)
    return {"train": train, "val": val, "test": test}


def build_system_crops(
    label: dict,
    img_path: Path,
    crops_dir: Path,
    labels_dir: Path,
) -> list[dict]:
    """악보 1곡 → 시스템 단위 크롭 이미지 + 라벨 저장.

    Returns:
        시스템별 {"hymn_id", "system", "label_path"} 목록
    """
    measures = label["measures"]
    hymn_id = label["hymn_id"]

    boundaries = find_system_boundaries(img_path)
    num_sys = len(boundaries)

    # 마디를 시스템에 균등 배분 (나머지는 마지막 시스템에)
    base = len(measures) // num_sys
    remainder = len(measures) % num_sys
    sys_measure_counts = [base + (1 if i < remainder else 0) for i in range(num_sys)]

    items = []
    m_idx = 0
    for sys_idx, ((y0, y1), count) in enumerate(zip(boundaries, sys_measure_counts)):
        sys_measures = measures[m_idx : m_idx + count]
        m_idx += count
        if not sys_measures:
            continue

        # 크롭 이미지 저장
        crop_img = crop_system(img_path, y0, y1)
        crop_path = crops_dir / f"hymn{hymn_id}_s{sys_idx}.png"
        crop_img.save(str(crop_path))

        # 시스템 라벨 저장
        sys_label = {
            "hymn_id": hymn_id,
            "system": sys_idx,
            "image_path": str(crop_path),
            "time_signature": label["time_signature"],
            "key_signature": label["key_signature"],
            "measures": sys_measures,
        }
        label_path = labels_dir / f"hymn{hymn_id}_s{sys_idx}.json"
        label_path.write_text(json.dumps(sys_label, ensure_ascii=False, indent=2), encoding="utf-8")
        items.append({"hymn_id": hymn_id, "system": sys_idx, "label_path": str(label_path)})

    return items


def build_dataset(
    png_dir: Path = PNG_DIR,
    xml_dir: Path = XML_DIR,
    out_dir: Path = OUT_DIR,
) -> list[dict]:
    """전체 XML 처리 → 시스템 단위 크롭 + JSON 저장 → splits.json 저장."""
    out_dir.mkdir(parents=True, exist_ok=True)
    labels_dir = out_dir / "labels"
    crops_dir = out_dir / "crops"
    labels_dir.mkdir(exist_ok=True)
    crops_dir.mkdir(exist_ok=True)

    items: list[dict] = []
    failed: list[str] = []
    xml_files = sorted(xml_dir.glob("새찬송가_*.xml"))
    for xml_path in xml_files:
        try:
            label = parse_xml(xml_path)
        except Exception as e:
            log.warning("SKIP %s: %s", xml_path.name, e)
            failed.append(xml_path.name)
            continue
        img_path = Path(label["image_path"])
        if not img_path.exists():
            log.warning("이미지 없음: %s", img_path)
            failed.append(xml_path.name)
            continue
        sys_items = build_system_crops(label, img_path, crops_dir, labels_dir)
        items.extend(sys_items)

    splits = split_dataset(items)
    splits_path = out_dir / "splits.json"
    splits_path.write_text(json.dumps(splits, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("완료: 곡 %d개 → 시스템 %d개 (실패 %d)", len(xml_files) - len(failed), len(items), len(failed))
    return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build_dataset()
