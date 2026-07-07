from pathlib import Path
import pytest
from app.core.errors import OmrError
from app.stages.omr.homr_adapter import HomrAdapter


def test_missing_image_raises(tmp_path):
    with pytest.raises(OmrError):
        HomrAdapter(work_dir=tmp_path).recognize(tmp_path / "nope.png")


def test_homr_binary_missing_raises(tmp_path, monkeypatch):
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)  # 더미(존재만 확인)
    monkeypatch.setattr("app.stages.omr.homr_adapter.config.homr_bin",
                        lambda: str(tmp_path / "no_such_homr"))
    with pytest.raises(OmrError):
        HomrAdapter(work_dir=tmp_path).recognize(img)


def test_recognize_returns_musicxml_on_success(tmp_path, monkeypatch):
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    fake_bin = tmp_path / "homr"
    fake_bin.write_text("#!/bin/sh\n")  # 존재만 하면 됨(run은 모킹)

    monkeypatch.setattr("app.stages.omr.homr_adapter.config.homr_bin",
                        lambda: str(fake_bin))

    # subprocess.run 모킹: homr가 <stem>.musicxml을 만든 것처럼 흉내
    def fake_run(cmd, **kw):
        img_arg = Path(cmd[-1])
        img_arg.with_suffix(".musicxml").write_text("<score-partwise/>")
        class R: returncode = 0; stderr = ""
        return R()
    monkeypatch.setattr("app.stages.omr.homr_adapter.subprocess.run", fake_run)

    out = HomrAdapter(work_dir=tmp_path).recognize(img)
    assert out.exists() and out.suffix == ".musicxml"


def test_nonzero_returncode_raises(tmp_path, monkeypatch):
    img = tmp_path / "in.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    fake_bin = tmp_path / "homr"; fake_bin.write_text("#!/bin/sh\n")
    monkeypatch.setattr("app.stages.omr.homr_adapter.config.homr_bin",
                        lambda: str(fake_bin))
    def fake_run(cmd, **kw):
        class R: returncode = 1; stderr = "boom"
        return R()
    monkeypatch.setattr("app.stages.omr.homr_adapter.subprocess.run", fake_run)
    with pytest.raises(OmrError):
        HomrAdapter(work_dir=tmp_path).recognize(img)
