"""Fixtures every suite can reach.

The shop fixtures live in tests/support/shop.py and are loaded as a plugin
rather than imported, because importing a fixture into a module shadows the
name and the linter is right to complain about it.
"""

pytest_plugins = ["tests.support.shop"]
