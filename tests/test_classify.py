"""Classification rules on activity codes."""

from rcpro.classify import ACT_2019, classify_one


def test_architect_settled_by_code():
    assert classify_one("architects", [("71111", "MAIN"), ("70200", "SECO")]) == ("yes", ["71111 MAIN"], ACT_2019)


def test_engineer_construction_wins_over_industry():
    codes = [("71121", "MAIN"), ("25110", "SECO"), ("43210", "SECO")]
    assert classify_one("engineers", codes) == ("likely", ["43210 SECO"], ACT_2019)


def test_engineer_industry_only_is_unlikely():
    assert classify_one("engineers", [("71121", "MAIN"), ("62100", "SECO")]) == ("unlikely", ["62100 SECO"], None)


def test_engineer_generic_codes_stay_unknown_without_evidence():
    codes = [("71121", "MAIN"), ("70200", "SECO"), ("71209", "SECO")]
    assert classify_one("engineers", codes) == ("unknown", [], None)
