"""timing.py 기능 테스트."""
from app.domain.score import Score, Voice, Note, VoiceName
from app.core.timing import build_timing


def _score():
    """테스트용 Score 팩토리."""
    return Score(voices={
        VoiceName.SOPRANO: Voice(
            name=VoiceName.SOPRANO,
            notes=[Note(pitch="F4", quarter_length=1.0),
                   Note(pitch="A4", quarter_length=2.0)],
        )
    })


def test_timing_start_end():
    """timing 이벤트의 start_sec, end_sec 계산 검증."""
    t = build_timing(_score(), bpm=60)
    notes = t["voices"]["soprano"]
    assert notes[0]["start_sec"] == 0.0
    assert notes[0]["end_sec"] == 1.0    # 1박 @ 60BPM = 1초
    assert notes[1]["start_sec"] == 1.0
    assert notes[1]["end_sec"] == 3.0    # 2박


def test_timing_pitch():
    """timing 이벤트의 pitch 필드 검증."""
    t = build_timing(_score(), bpm=60)
    assert t["voices"]["soprano"][0]["pitch"] == "F4"


def test_timing_api(isolate_store, tmp_path):
    """GET /jobs/{id}/timing 엔드포인트 검증."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.storage.store import store
    from app.orchestration.job import Job, JobStatus
    import json

    tj = tmp_path / "timing.json"
    tj.write_text(json.dumps({"bpm": 80, "voices": {}}))
    store._jobs["j1"] = Job(id="j1", status=JobStatus.DONE, timing_path=str(tj))
    resp = TestClient(app).get("/jobs/j1/timing")
    assert resp.status_code == 200
    assert resp.json()["bpm"] == 80
