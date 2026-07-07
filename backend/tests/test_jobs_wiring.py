import inspect
from app.api.routes import jobs


def test_run_uses_homr_adapter():
    """배선(_run)이 HomrAdapter를 사용해야 한다(Audiveris 아님)."""
    src = inspect.getsource(jobs._run)
    assert "HomrAdapter" in src
    assert "AudiverisAdapter" not in src
