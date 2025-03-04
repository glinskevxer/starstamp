from .conftest import Invoke


def test_the_defaults_show(shop: Invoke) -> None:
    out = shop("setting", "list").output
    assert "capacity_per_rig" in out
    assert "24" in out


def test_setting_one(shop: Invoke) -> None:
    out = shop("setting", "set", "capacity_per_rig", "40", "--from", "2024-01-01").output
    assert "capacity_per_rig = 40 from 2024-01-01" in out
    assert "40" in shop("--today", "2024-06-12", "setting", "list").output


def test_a_value_outside_its_range(shop: Invoke) -> None:
    shop("setting", "set", "capacity_per_rig", "900", expect=2)


def test_a_setting_the_shop_does_not_have(shop: Invoke) -> None:
    shop("setting", "set", "wobble", "3", expect=2)


def test_the_history(shop: Invoke) -> None:
    assert "has never been set" in shop("setting", "history", "capacity_per_rig").output
    shop("setting", "set", "capacity_per_rig", "30", "--from", "2023-01-01")
    shop("setting", "set", "capacity_per_rig", "40", "--from", "2024-01-01", "--by", "jt7")
    out = shop("setting", "history", "capacity_per_rig").output
    assert "= 30 from 2023-01-01" in out
    assert "= 40 from 2024-01-01" in out


def test_setting_it_twice_from_one_day(shop: Invoke) -> None:
    shop("setting", "set", "minimum_hold_seconds", "60", "--from", "2024-01-01")
    shop("setting", "set", "minimum_hold_seconds", "90", "--from", "2024-01-01", expect=4)
