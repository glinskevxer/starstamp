"""Fixtures every suite can reach.

The shop fixtures live in tests/support/shop.py and are loaded as a plugin
rather than imported, because importing a fixture into a module shadows the
name and the linter is right to complain about it.
"""

from hypothesis import HealthCheck, settings

pytest_plugins = ["tests.support.shop"]

# The properties in tests/property are pure arithmetic and pure rules, so the
# only thing hypothesis's deadline measures here is how busy the machine is.
# It has failed a build once for that reason and would do it again.
settings.register_profile(
    "starstamp",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("starstamp")
