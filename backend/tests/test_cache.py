import pytest
import cache


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path):
    # Each test gets its own fresh SQLite file so tests never share state.
    original = cache.DB
    cache.DB = str(tmp_path / "test.db")
    cache.init()
    yield
    cache.DB = original


def test_get_missing_brand_returns_none():
    assert cache.get("unknownbrand") is None


def test_put_then_get_round_trips():
    payload = {"ethics_score": 72, "ownership_score": 60, "summary": "Good."}
    cache.put("patagonia", payload)
    result = cache.get("patagonia")
    assert result["ethics_score"] == 72
    assert result["ownership_score"] == 60


def test_brand_key_is_case_insensitive():
    cache.put("Nike", {"ethics_score": 40})
    assert cache.get("nike") is not None
    assert cache.get("NIKE") is not None


def test_put_overwrites_existing_entry():
    cache.put("zara", {"ethics_score": 30})
    cache.put("zara", {"ethics_score": 55})
    result = cache.get("zara")
    assert result["ethics_score"] == 55


def test_get_returns_none_after_fresh_init():
    # Regression: init() should create the table but not pre-populate it.
    assert cache.get("adidas") is None
