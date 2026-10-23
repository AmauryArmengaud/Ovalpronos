"""
Pixel 7 device emulation for all e2e tests.
"""
import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Override browser context with Pixel 7 mobile profile for every test."""
    return {
        **browser_context_args,
        "viewport": {"width": 412, "height": 915},
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "has_touch": True,
        "is_mobile": True,
    }
