import pytest


@pytest.fixture(autouse=True)
def _any_past_day_is_loggable(monkeypatch, request):
    """Most tests log on the fixture menu's fixed date (2026-10-08), weeks ago by now. Lift the
    one-week backfill limit for them; tests marked `backfill_limit` keep it."""
    if "backfill_limit" in request.keywords:
        return
    import app.main as main

    monkeypatch.setattr(main, "BACKFILL_DAYS", 100_000)


def pytest_configure(config):
    config.addinivalue_line("markers", "backfill_limit: keep the real one-week limit on logging past days")
