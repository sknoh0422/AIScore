from fastapi.testclient import TestClient
from app.main import app

def test_create_and_get_job():
    client = TestClient(app)
    files = {"file": ("s.png", b"fakebytes", "image/png")}
    r = client.post("/jobs", files=files)
    assert r.status_code == 201
    job_id = r.json()["id"]
    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["status"] in {"queued","omr","parsing","synth","mixing","done","failed"}
