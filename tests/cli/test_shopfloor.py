from .conftest import Invoke


def test_facility_add_and_show(shop: Invoke) -> None:
    shop(
        "facility",
        "add",
        "a419",
        "Wasatch Cylinder Service",
        "--from",
        "2021-05-01",
        "--until",
        "2026-04-30",
        "--methods",
        "volumetric,proof,visual",
        "--address",
        "1400 S Gladiola St",
    )
    out = shop("--today", "2024-06-12", "facility", "show").output
    assert "A419" in out
    assert "in force  yes" in out
    assert "external visual, proof pressure, volumetric" in out


def test_a_lapsed_rin_reads_as_out_of_force(shop: Invoke) -> None:
    shop(
        "facility",
        "add",
        "a419",
        "Wasatch",
        "--from",
        "2016-05-01",
        "--until",
        "2021-04-30",
        "--methods",
        "volumetric",
    )
    assert "in force  no" in shop("--today", "2024-06-12", "facility", "show").output


def test_renewing_a_rin(shop: Invoke) -> None:
    shop(
        "facility",
        "add",
        "a419",
        "Wasatch",
        "--from",
        "2021-05-01",
        "--until",
        "2026-04-30",
        "--methods",
        "volumetric",
    )
    assert "approved to 2031-04-30" in shop("facility", "renew", "a419", "2031-04-30").output


def test_the_bench(shop: Invoke) -> None:
    assert "nobody on the bench" in shop("tech", "list").output
    shop(
        "tech",
        "add",
        "jt7",
        "Jesse Tovar",
        "--methods",
        "volumetric,visual",
        "--from",
        "2022-03-01",
    )
    out = shop("tech", "list").output
    assert "JT7" in out
    assert "external_visual, volumetric" in out


def test_a_technician_signed_off_for_nothing_is_refused(shop: Invoke) -> None:
    shop("tech", "add", "jt7", "Jesse Tovar", "--methods", "", expect=2)


def test_rig_certificates_and_checks(shop: Invoke) -> None:
    shop(
        "rig",
        "certify",
        "wj-1",
        "gauge",
        "--serial",
        "PG-4",
        "--issued",
        "2024-01-15",
        "--until",
        "2029-01-15",
        "--by",
        "Rocky Mountain Calibration",
    )
    out = shop("--today", "2024-06-12", "rig", "status", "WJ-1").output
    assert "pressure_indicator" in out
    assert "no start of day check" in out
    shop("rig", "check", "WJ-1", "40.0", "40.1", "--on", "2024-06-12", "--tech", "jt7")
    assert "within tolerance" in shop("--today", "2024-06-12", "rig", "status", "WJ-1").output


def test_a_check_out_of_tolerance_says_so_loudly(shop: Invoke) -> None:
    out = shop("rig", "check", "WJ-1", "40.0", "38.0", "--on", "2024-06-12").output
    assert "OUT OF TOLERANCE" in out


def test_two_checks_the_same_day_are_refused(shop: Invoke) -> None:
    shop("rig", "check", "WJ-1", "40.0", "40.1", "--on", "2024-06-12")
    shop("rig", "check", "WJ-1", "40.0", "40.2", "--on", "2024-06-12", expect=4)


def test_a_rig_with_nothing_on_file(shop: Invoke) -> None:
    assert "no certificates on file" in shop("rig", "status", "WJ-9").output


def test_showing_one_technician(shop: Invoke) -> None:
    shop(
        "tech",
        "add",
        "jt7",
        "Jesse Tovar",
        "--methods",
        "volumetric,visual",
        "--from",
        "2022-03-01",
    )
    out = shop("--today", "2024-06-12", "tech", "show", "jt7").output
    assert "Jesse Tovar" in out
    assert "current     yes" in out
    assert "external visual, volumetric" in out


def test_showing_somebody_who_is_not_on_the_bench(shop: Invoke) -> None:
    shop("tech", "show", "zz9", expect=3)
