from __future__ import annotations

def pytest_addoption(parser) -> None:
    # Ensure pytest recognizes asyncio_mode even when pytest-asyncio is not installed.
    parser.addini("asyncio_mode", help="Asyncio plugin mode", default="auto")
