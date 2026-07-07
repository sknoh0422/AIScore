"""eval_baseline 핵심 지표 함수 단위 테스트."""
from __future__ import annotations

from training.scripts.eval_baseline import (
    edit_distance,
    seq_error_rate,
    pitch_bag_prf,
)


# ── edit_distance ────────────────────────────────────────────────────────────

def test_edit_distance_identical():
    assert edit_distance(["C4", "E4"], ["C4", "E4"]) == 0


def test_edit_distance_substitution():
    assert edit_distance(["C4", "E4"], ["C4", "F4"]) == 1


def test_edit_distance_insert_delete():
    assert edit_distance(["C4"], ["C4", "E4"]) == 1
    assert edit_distance(["C4", "E4"], ["C4"]) == 1


def test_edit_distance_empty():
    assert edit_distance([], ["C4"]) == 1
    assert edit_distance([], []) == 0


# ── seq_error_rate (SER) ─────────────────────────────────────────────────────

def test_ser_zero_when_identical():
    assert seq_error_rate(["C4", "E4", "G4"], ["C4", "E4", "G4"]) == 0.0


def test_ser_one_when_all_wrong():
    assert seq_error_rate(["C4", "E4"], ["F5", "G5"]) == 1.0


def test_ser_empty_ref_with_pred():
    # 정답이 비어있는데 예측이 있으면 전부 삽입 오류
    assert seq_error_rate([], ["C4"]) == 1.0


# ── pitch_bag_prf ────────────────────────────────────────────────────────────

def test_bag_prf_perfect():
    p, r, f = pitch_bag_prf(["C4", "E4", "C4"], ["C4", "E4", "C4"])
    assert p == r == f == 1.0


def test_bag_prf_half_recall():
    # 정답 4개 중 2개만 예측
    p, r, f = pitch_bag_prf(["C4", "E4", "G4", "C5"], ["C4", "E4"])
    assert p == 1.0
    assert r == 0.5


def test_bag_prf_multiset_counts():
    # 정답에 C4가 2번인데 예측에 1번이면 recall에 반영
    p, r, f = pitch_bag_prf(["C4", "C4"], ["C4"])
    assert r == 0.5
    assert p == 1.0


def test_bag_prf_empty_pred():
    p, r, f = pitch_bag_prf(["C4"], [])
    assert (p, r, f) == (0.0, 0.0, 0.0)
