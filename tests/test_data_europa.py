from ropublicdata.sources import data_europa


def test_search_romania_datasets_basic_query():
    result = data_europa.search_romania_datasets(query="buget", limit=3)
    assert result["total"] > 0
    assert 0 < len(result["results"]) <= 3
    first = result["results"][0]
    assert first["title"]
    assert first["url"].startswith("https://data.europa.eu/data/datasets/")


def test_search_romania_datasets_browse_all():
    # Empty query browses most-recently-updated RO datasets instead of
    # searching -- this is a real API quirk (q="*" matches nothing on the
    # current API, unlike most search APIs), see the module docstring.
    result = data_europa.search_romania_datasets(query="", limit=5)
    assert result["total"] > 1000  # RO has thousands of datasets on this portal
    assert len(result["results"]) == 5


def test_search_romania_datasets_limit_is_capped():
    result = data_europa.search_romania_datasets(query="", limit=9999)
    assert len(result["results"]) <= data_europa.MAX_LIMIT
