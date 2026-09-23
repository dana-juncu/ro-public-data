import pytest

from ropublicdata.sources import amccrs


def test_search_buildings_no_filters():
    result = amccrs.search_buildings(limit=5)
    assert result["total_matches"] > 2000  # whole registry, ~2,796 as of Sept 2026
    assert len(result["buildings"]) == 5
    first = result["buildings"][0]
    assert first["address"]
    assert first["sector"].startswith("Sector")


def test_search_buildings_filters_by_sector_and_risk():
    result = amccrs.search_buildings(sector="Sector 3", risk_class="RsI", limit=50)
    assert result["total_matches"] > 0
    assert all(b["sector"] == "Sector 3" for b in result["buildings"])
    assert all(b["risk_class"] == "RsI" for b in result["buildings"])


def test_search_buildings_filters_by_street_substring():
    result = amccrs.search_buildings(street="academiei", limit=50)
    assert result["total_matches"] > 0
    assert all("academiei" in b["address"].lower() for b in result["buildings"])


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("3.Clasa de risc seismic RsIII.", "RsIII"),
        ("1.RSI.", "RsI"),
        ("RsIV", "RsIV"),
        ("5.CONSOLIDATE", "consolidated"),
        ("CONSOLIDATE", "consolidated"),
        (
            "INCADRARE IN CATEGORIE DE URGENTA; NEINCADRATE IN CLASE DE RISC "
            "SEISMIC CORESPUNZATOARE",
            "pending",
        ),
        ("", "unknown"),
        ("Popescu V. Dumitru Dan", "unknown"),  # a real data-entry artifact
    ],
)
def test_risk_class_normalization(raw, expected):
    """
    Offline unit test (no network) for the risk-class normalizer -- see
    its docstring in sources/amccrs.py for why this mapping exists: only
    ~59% of the real registry is actually RsI-RsIV, and naively extracting
    'Rs...' text left the rest either blank or as an unnormalized raw
    Romanian status phrase, which breaks exact-match filtering by design.
    """
    assert amccrs._risk_class(raw) == expected


def test_search_buildings_risk_class_filter_covers_all_categories():
    """Every normalized risk_class value should be filterable, not just the
    RsI-RsIV ones -- this is the actual bug this normalization fixed."""
    for risk_class in ("pending", "consolidated"):
        result = amccrs.search_buildings(risk_class=risk_class, limit=5)
        assert result["total_matches"] > 0, f"no buildings matched risk_class={risk_class!r}"
