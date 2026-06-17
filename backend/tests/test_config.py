import os
from app.core import config

def test_defaults_present():
    assert config.omr_min_long_edge() >= 1500
    assert "audiveris" in config.audiveris_bin().lower()

def test_env_override(monkeypatch):
    monkeypatch.setenv("AISCORE_OMR_MIN_LONG_EDGE", "1800")
    assert config.omr_min_long_edge() == 1800
