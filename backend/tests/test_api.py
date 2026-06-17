import io
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app

def _png_bytes():
    buf = io.BytesIO(); Image.new("RGB", (10, 10), "white").save(buf, "PNG"); return buf.getvalue()

def test_create_and_get_job():
    client = TestClient(app)
    r = client.post("/jobs", files={"file": ("s.png", _png_bytes(), "image/png")})
    assert r.status_code == 201
    job_id = r.json()["id"]
    r2 = client.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["status"] in {"queued","omr","parsing","synth","mixing","done","failed"}

def test_rejects_non_image():
    client = TestClient(app)
    r = client.post("/jobs", files={"file": ("x.png", b"notanimage", "image/png")})
    assert r.status_code == 400
