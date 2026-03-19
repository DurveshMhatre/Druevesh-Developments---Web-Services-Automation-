"""Pytest configuration and shared fixtures."""

def pytest_addoption(parser):
    """Add custom CLI options for test configuration."""
    parser.addoption(
        "--runintegration",
        action="store_true",
        default=False,
        help="Run integration tests that require external services",
    )
