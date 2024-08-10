import pytest

from starstamp.errors import ValidationError
from starstamp.model.money import Money, total


@pytest.mark.parametrize(
    ("text", "cents"),
    [("14.50", 1450), ("$14.50", 1450), ("14", 1400), ("14.5", 1450), ("0.07", 7)],
)
def test_amounts_parse(text: str, cents: int) -> None:
    assert Money.parse(text).cents == cents


@pytest.mark.parametrize("text", ["", "14.505", "-4", "fourteen"])
def test_bad_amounts(text: str) -> None:
    with pytest.raises(ValidationError, match="looks like"):
        Money.parse(text)


def test_negative_money_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot be negative"):
        Money(-1)


def test_arithmetic() -> None:
    assert Money.parse("14.50").plus(Money.parse("0.75")).cents == 1525
    assert Money.parse("14.50").times(3).cents == 4350
    assert Money.parse("14.50").times(0) == Money.zero()


def test_a_negative_count_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative count"):
        Money.parse("14.50").times(-1)


def test_shares_round_half_up_and_add_back() -> None:
    amount = Money.parse("10.00")
    thirds = [amount.share_of(1, 3) for _ in range(3)]
    assert [item.cents for item in thirds] == [333, 333, 333]
    assert amount.share_of(2, 3).cents == 667


def test_a_share_of_nothing() -> None:
    with pytest.raises(ValidationError, match="share of nothing"):
        Money.parse("10.00").share_of(1, 0)


def test_totals() -> None:
    assert total([Money.parse("14.50"), Money.parse("0.75")]).cents == 1525
    assert total([]) == Money.zero()


def test_text_forms() -> None:
    assert str(Money.parse("14.50")) == "14.50"
    assert Money.parse("14.05").with_symbol() == "$14.05"
    assert str(Money(7)) == "0.07"


def test_ordering() -> None:
    assert Money.parse("1.00") < Money.parse("1.01")
    assert max([Money.parse("1.00"), Money.parse("9.99")]) == Money.parse("9.99")
