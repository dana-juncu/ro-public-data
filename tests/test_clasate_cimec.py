from ropublicdata.sources import clasate_cimec


def test_search_items_known_query():
    result = clasate_cimec.search_items(query="Brancusi", page=1)
    assert result["total_matches"] > 0
    assert result["page"] == 1
    assert len(result["items"]) > 0
    first = result["items"][0]
    assert first["k"]  # stable key needed for get_item_detail()
    assert first["url"].startswith(clasate_cimec.BASE)


def test_search_items_pagination():
    page1 = clasate_cimec.search_items(clasificare="tez", page=1)
    page2 = clasate_cimec.search_items(clasificare="tez", page=2)
    assert page1["total_matches"] == page2["total_matches"]
    ids_page1 = {i["k"] for i in page1["items"]}
    ids_page2 = {i["k"] for i in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_get_item_detail_from_a_real_search_result():
    results = clasate_cimec.search_items(query="Brancusi", page=1)
    first = results["items"][0]
    detail = clasate_cimec.get_item_detail(first["k"], first["tit"])
    assert detail["k"] == first["k"]
    assert detail["fields"]  # at least some Label: value fields parsed
    assert detail["license"] == "CC BY-SA 4.0"
