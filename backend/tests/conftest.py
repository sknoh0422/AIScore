import pytest
from app.storage.store import store

@pytest.fixture(autouse=True)
def isolate_store(tmp_path):
    """각 테스트마다 store를 초기화하고 tmp 디렉터리를 사용."""
    store.reset(root=tmp_path / "jobs")
    yield
    store.reset()
