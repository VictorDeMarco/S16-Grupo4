from src.betting import adjust_bet, allowed_options_for_round, validate_bets


def test_allowed_options_per_round():
    assert allowed_options_for_round(1) == 4
    assert allowed_options_for_round(4) == 4
    assert allowed_options_for_round(5) == 3
    assert allowed_options_for_round(7) == 3
    assert allowed_options_for_round(8) == 2


def test_adjust_bet_cannot_exceed_money():
    bets = {"A": 975000, "B": 0, "C": 0, "D": 0}
    result = adjust_bet(bets, "A", 1, money_total=1_000_000)
    assert not result.valid


def test_non_final_round_must_leave_empty_trapdoor():
    bets = {"A": 25000, "B": 25000, "C": 25000, "D": 25000}
    result = validate_bets(bets, money_total=100000, is_final_round=False)
    assert not result.valid


def test_final_round_can_fill_all_options():
    bets = {"A": 25000, "B": 25000}
    result = validate_bets(bets, money_total=50000, is_final_round=True)
    assert result.valid


def test_bets_must_be_multiple_of_block():
    bets = {"A": 30000, "B": 0, "C": 0, "D": 0}
    result = validate_bets(bets, money_total=30000, is_final_round=False)
    assert not result.valid
