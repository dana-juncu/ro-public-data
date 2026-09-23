"""
Shared pytest config.

Every test in this suite is a real, live call against the actual public
endpoint — there are no mocks and no fixtures/cassettes, on purpose: the
whole point of this project is "does the real endpoint still respond the
way we think it does", and a mocked test would just re-assert our own
assumptions back at us. That means this suite needs network access and
will fail if a source is genuinely down or has changed shape — see
CONTRIBUTING.md's "When a source breaks" section for what to do then.

Kept deliberately light on each source (small limits, single lookups,
narrow date ranges) to be a polite, infrequent caller of these free,
keyless government/public endpoints — this suite is meant to run on push/
PR and on a periodic CI schedule, not in a tight loop.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """Tag every test in this package as 'live' so `pytest -m live` (or
    `-m "not live"` to skip all of them, e.g. offline) works without each
    test file repeating the marker."""
    for item in items:
        item.add_marker(pytest.mark.live)
