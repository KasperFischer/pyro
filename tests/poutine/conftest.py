import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if item.nodeid.startswith("tests/poutine"):
            if "stage" not in item.keywords:
                item.add_marker(pytest.mark.stage("unit"))
            if "init" not in item.keywords:
                item.add_marker(pytest.mark.init(rng_seed=123))
