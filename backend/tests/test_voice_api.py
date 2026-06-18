"""성부별 WAV 엔드포인트 테스트."""
from fastapi.testclient import TestClient
from app.main import app
from app.storage.store import store
from app.orchestration.job import Job


def test_audio_voice_not_found(tmp_path):
    client = TestClient(app)
    store._jobs["j1"] = Job(id="j1", status="done")
    resp = client.get("/jobs/j1/audio/soprano")
    assert resp.status_code == 404


def test_audio_voice_returns_wav(tmp_path):
    client = TestClient(app)
    wav = tmp_path / "soprano.wav"
    wav.write_bytes(b"RIFF")
    store._jobs["j1"] = Job(
        id="j1", status="done",
        voice_paths={"soprano": str(wav)}
    )
    resp = client.get("/jobs/j1/audio/soprano")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
