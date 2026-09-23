from ropublicdata.sources import ins_tempo

# POP105A: resident population by age/sex/urban-rural/region/year -- a
# stable, well-known matrix, confirmed live during the original
# investigation (see FINDINGS.md). Selections below are
# Total/Total/Total/TOTAL(Romania)/2025/persons.
POP105A_TOTAL_2025_SELECTIONS = [1, 105, 108, 112, 4912, 9685]


def test_browse_full_tree():
    result = ins_tempo.browse()
    assert len(result["categories"]) > 100
    assert all("code" in c and "name" in c for c in result["categories"])


def test_browse_drill_into_category():
    tree = ins_tempo.browse()
    # Drill into the first category that has children, whatever it's called
    # this run -- more robust than hardcoding a specific code/name.
    parent = next(c for c in tree["categories"] if not c["is_matrix"])
    result = ins_tempo.browse(parent["code"])
    assert result["code"] == parent["code"]
    assert isinstance(result["children"], list)


def test_matrix_dimensions_pop105a():
    dims = ins_tempo.matrix_dimensions("POP105A")
    assert dims["title"]
    assert len(dims["dimensions"]) == len(POP105A_TOTAL_2025_SELECTIONS)
    assert all(d["options"] for d in dims["dimensions"])


def test_query_pop105a_matches_known_population():
    rows = ins_tempo.query("POP105A", POP105A_TOTAL_2025_SELECTIONS)
    assert len(rows) == 1
    value = rows[0]["Valoare"]
    # Romania's real total resident population, 1 Jan 2025 (~19.04M) --
    # confirmed exact during the original investigation; allow a wide band
    # here since INS could later revise the published figure slightly.
    assert 18_000_000 < value < 20_500_000
