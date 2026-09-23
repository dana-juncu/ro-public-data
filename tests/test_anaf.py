from ropublicdata.sources import anaf

# Real, stable, well-known CUIs -- large companies that aren't going away,
# so these are safe to keep hardcoded as a live smoke check.
DANTE_INTERNATIONAL_CUI = 14399840  # eMAG
OMV_PETROM_CUI = 1590082


def test_get_company_known_cui():
    company = anaf.get_company(DANTE_INTERNATIONAL_CUI)
    assert company is not None
    assert company.get("date_generale", {}).get("cui") == DANTE_INTERNATIONAL_CUI


def test_get_company_unknown_cui_returns_none():
    # CUI 1 is below Romania's real allocation range -- ANAF has no record for it.
    assert anaf.get_company(1) is None


def test_get_companies_batch():
    results = anaf.get_companies([DANTE_INTERNATIONAL_CUI, OMV_PETROM_CUI])
    assert len(results) == 2
    cuis = {r["date_generale"]["cui"] for r in results}
    assert cuis == {DANTE_INTERNATIONAL_CUI, OMV_PETROM_CUI}


def test_get_companies_rejects_over_100():
    import pytest

    with pytest.raises(ValueError):
        anaf.get_companies(list(range(101)))
