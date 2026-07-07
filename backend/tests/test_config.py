import os
from app.core import config

def test_defaults_present():
    assert config.omr_min_long_edge() >= 1500
    assert "audiveris" in config.audiveris_bin().lower()

def test_env_override(monkeypatch):
    monkeypatch.setenv("AISCORE_OMR_MIN_LONG_EDGE", "1800")
    assert config.omr_min_long_edge() == 1800

def test_homr_bin_default_points_to_sibling_venv():
    from app.core import config
    b = config.homr_bin()
    assert b.endswith("homr/.venv/bin/homr")

def test_homr_bin_env_override(monkeypatch):
    from app.core import config
    monkeypatch.setenv("AISCORE_HOMR_BIN", "/custom/homr")
    assert config.homr_bin() == "/custom/homr"
