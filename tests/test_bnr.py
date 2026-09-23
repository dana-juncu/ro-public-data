from ropublicdata.sources import bnr


def test_get_latest_rates():
    result = bnr.get_latest_rates()
    assert "date" in result and result["date"]
    assert "rates" in result
    assert "EUR" in result["rates"]
    eur = result["rates"]["EUR"]
    # Sanity band rather than an exact value -- the real rate moves daily.
    assert 4.5 < eur["rate_ron"] < 6.0
    assert eur["multiplier"] == 1


def test_get_last_10_days():
    days = bnr.get_last_10_days()
    assert len(days) >= 1
    assert all("EUR" in d["rates"] for d in days)
    # Each entry has its own date, oldest first.
    dates = [d["date"] for d in days]
    assert dates == sorted(dates)


def test_get_year_archive():
    # A year well in the past so the archive is guaranteed complete and stable.
    rows = bnr.get_year_archive(2020)
    assert len(rows) > 200  # roughly one per business day
    assert all("EUR" in d["rates"] for d in rows)
