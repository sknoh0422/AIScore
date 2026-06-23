import json
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

PNG_DIR = Path("score_images/png")
XML_DIR = Path("score_images/xml/분리")
SAMPLE_XML = XML_DIR / "새찬송가_001 만복의근원하나님.xml"


def _make_system_crop_png(tmp_path: Path, name: str = "hymn001_s0.png") -> Path:
    """treble(상단)·bass(하단) 두 스태프가 있는 합성 시스템 크롭."""
    w, h = 800, 280
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    for i in range(5):
        draw.line([(0, 30 + i * 7), (w - 1, 30 + i * 7)], fill=0, width=1)
    for x in range(20, w, 50):
        draw.ellipse([x - 4, 35, x + 4, 43], fill=0)
    for i in range(5):
        draw.line([(0, 190 + i * 7), (w - 1, 190 + i * 7)], fill=0, width=1)
    for x in range(20, w, 50):
        draw.ellipse([x - 4, 195, x + 4, 203], fill=0)
    p = tmp_path / name
    img.save(p)
    return p


def _make_system_label(tmp_path: Path, crop_path: Path, name: str = "hymn001_s0.json") -> Path:
    measures = [
        {
            "measure_num": 1,
            "S": [{"pitch": "E4", "duration": 1.0, "tie_start": False, "tie_end": False}],
            "A": [{"pitch": "C4", "duration": 1.0, "tie_start": False, "tie_end": False}],
            "T": [{"pitch": "G3", "duration": 1.0, "tie_start": False, "tie_end": False}],
            "B": [{"pitch": "C3", "duration": 1.0, "tie_start": False, "tie_end": False}],
        }
    ]
    label = {
        "hymn_id": "001",
        "system": 0,
        "image_path": str(crop_path),
        "time_signature": "4/4",
        "key_signature": 0,
        "measures": measures,
    }
    p = tmp_path / name
    p.write_text(json.dumps(label, ensure_ascii=False), encoding="utf-8")
    return p


def test_parse_xml_returns_required_keys():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    assert "hymn_id" in result
    assert "measures" in result
    assert len(result["measures"]) > 0


def test_parse_xml_measure_has_four_voices():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    m = result["measures"][0]
    for voice in ("S", "A", "T", "B"):
        assert voice in m, f"voice {voice} missing"


def test_parse_xml_note_has_required_fields():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    # measure 0은 전주(쉼표)일 수 있으니 첫 음표가 있는 마디 탐색
    note = None
    for m in result["measures"]:
        for v in ("S", "A", "T", "B"):
            if m[v]:
                note = m[v][0]
                break
        if note:
            break
    assert note is not None
    for field in ("pitch", "duration", "tie_start", "tie_end"):
        assert field in note, f"field {field} missing"


def test_split_dataset_ratios():
    from training.scripts.data_prep import split_dataset
    items = [{"hymn_id": str(i)} for i in range(100)]
    splits = split_dataset(items, seed=42)
    assert "train" in splits and "val" in splits and "test" in splits
    total = len(splits["train"]) + len(splits["val"]) + len(splits["test"])
    assert total == 100
    assert 75 <= len(splits["train"]) <= 82  # ~80%


# ── build_staff_crops ────────────────────────────────────────────────────────

def _setup_staff_crop_env(tmp_path: Path):
    """out_dir 구조를 만들고 시스템 크롭+라벨 1개를 배치."""
    out_dir     = tmp_path / "data"
    labels_dir  = out_dir / "labels"
    crops_dir   = out_dir / "crops"
    labels_dir.mkdir(parents=True)
    crops_dir.mkdir(parents=True)

    crop_path  = _make_system_crop_png(crops_dir, "hymn001_s0.png")
    _make_system_label(labels_dir, crop_path, "hymn001_s0.json")
    return out_dir


def test_build_staff_crops_returns_two_items_per_system(tmp_path):
    from training.scripts.data_prep import build_staff_crops
    out_dir = _setup_staff_crop_env(tmp_path)
    items = build_staff_crops(out_dir)
    assert len(items) == 2  # treble + bass


def test_build_staff_crops_staff_keys(tmp_path):
    from training.scripts.data_prep import build_staff_crops
    out_dir = _setup_staff_crop_env(tmp_path)
    items = build_staff_crops(out_dir)
    keys = {i["staff"] for i in items}
    assert keys == {"treble", "bass"}


def test_build_staff_crops_image_size(tmp_path):
    from training.scripts.data_prep import build_staff_crops, STAFF_IMG_H, STAFF_IMG_W
    out_dir = _setup_staff_crop_env(tmp_path)
    items = build_staff_crops(out_dir)
    for item in items:
        label = json.loads(Path(item["label_path"]).read_text())
        img = Image.open(label["image_path"])
        assert img.size == (STAFF_IMG_W, STAFF_IMG_H)


def test_build_staff_crops_treble_has_SA_only(tmp_path):
    from training.scripts.data_prep import build_staff_crops
    out_dir = _setup_staff_crop_env(tmp_path)
    items = build_staff_crops(out_dir)
    treble_item = next(i for i in items if i["staff"] == "treble")
    label = json.loads(Path(treble_item["label_path"]).read_text())
    m = label["measures"][0]
    assert "S" in m and "A" in m
    assert "T" not in m and "B" not in m


def test_build_staff_crops_bass_has_TB_only(tmp_path):
    from training.scripts.data_prep import build_staff_crops
    out_dir = _setup_staff_crop_env(tmp_path)
    items = build_staff_crops(out_dir)
    bass_item = next(i for i in items if i["staff"] == "bass")
    label = json.loads(Path(bass_item["label_path"]).read_text())
    m = label["measures"][0]
    assert "T" in m and "B" in m
    assert "S" not in m and "A" not in m


def test_build_staff_crops_splits_json_created(tmp_path):
    from training.scripts.data_prep import build_staff_crops
    out_dir = _setup_staff_crop_env(tmp_path)
    build_staff_crops(out_dir)
    splits_path = out_dir / "splits_staff.json"
    assert splits_path.exists()
    splits = json.loads(splits_path.read_text())
    assert "train" in splits or "val" in splits or "test" in splits
